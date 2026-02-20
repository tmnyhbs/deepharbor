import time
import datetime
import signal
import sys
import socket
import ipaddress
import psycopg2
from uhppoted import uhppote
from pprint import pprint

from config import config
from dhs_logging import logger

###############################################################################
# Configuration
###############################################################################

BOARD_SERIAL = int(config['rfid_board']['BOARD_SERIAL_NUMBER_AS_INT'])
BOARD_IP = config['rfid_board']['BOARD_IP']
BOARD_PORT = int(config['rfid_board']['BOARD_PORT'])

bind = "0.0.0.0"
broadcast = f'255.255.255.255:{BOARD_PORT}'
listen = f'0.0.0.0:{BOARD_PORT}'

host_addr = ipaddress.IPv4Address(BOARD_IP)
board_tuple = (BOARD_SERIAL, str(host_addr), 'tcp')

board = uhppote.Uhppote(bind=bind,
                        broadcast=broadcast,
                        listen=listen,
                        debug=False)

###############################################################################
# Shutdown
###############################################################################

_shutdown_requested = False

def _handle_shutdown(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    _shutdown_requested = True

signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)

###############################################################################
# Database
###############################################################################

def get_db_connection():
    return psycopg2.connect(
        dbname=config['Database']['name'],
        user=config['Database']['user'],
        password=config['Database']['password'],
        host=config['Database']['host'],
        port=config['Database']['port']
    )

def get_last_rfid_event_timestamp(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT timestamp FROM member_access_log ORDER BY timestamp DESC LIMIT 1;"
        )
        record = cursor.fetchone()
    return record[0] if record else None

def insert_rfid_event(conn, card, door, access_granted, event_type, timestamp):
    insert_query = """
        INSERT INTO member_access_log
        (member_id, rfid_tag, access_point, access_granted, board_tag_num, timestamp)
        SELECT  g.id,
                g.tag_id,
                %s,
                %s,
                %s,
                %s
        FROM    get_member_by_rfid_tag(%s) g
        ON CONFLICT (rfid_tag, board_tag_num, access_point, access_granted, timestamp)
        DO NOTHING;
    """
    with conn.cursor() as cursor:
        cursor.execute(insert_query, (door, access_granted, card, timestamp, card))
    conn.commit()
    logger.info(
        f"Inserted event: {timestamp}, Door: {door}, "
        f"Type: {event_type}, Card: {card}, Granted: {access_granted}"
    )

###############################################################################
# Helpers
###############################################################################

def is_valid_event(card, event_type):
    """Card 10 is a board sentinel value. Event type 255 means no event."""
    return card != 10 and event_type != 255

def get_local_ip():
    """Determine the local IP address used to route packets toward the board."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # connect() on a UDP socket does not send anything; it only sets
        # the local interface for routing purposes.
        s.connect((BOARD_IP, 1))
        return s.getsockname()[0]
    finally:
        s.close()

def db_insert_with_retry(db_conn_holder, card, door, access_granted, event_type, timestamp):
    """
    Insert an event into the DB, reconnecting up to 3 times on failure.
    db_conn_holder is a single-element list so the caller's reference is updated
    when a reconnect is needed.
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        conn = db_conn_holder[0]
        try:
            insert_rfid_event(conn, card, door, access_granted, event_type, timestamp)
            return
        except Exception as e:
            logger.error(f"DB insert failed (attempt {attempt}/{max_retries}): {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            if attempt < max_retries:
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    db_conn_holder[0] = get_db_connection()
                except Exception as reconnect_err:
                    logger.error(f"DB reconnect failed: {reconnect_err}")
                    time.sleep(2 ** attempt)
            else:
                logger.error(
                    f"Dropping event after {max_retries} DB failures: "
                    f"card={card}, ts={timestamp}"
                )

###############################################################################
# Startup backfill
#
# Scan the board's event log once at startup to catch any events that occurred
# while this service was not running. Uses conservative 1-second delays between
# requests to avoid overwhelming the embedded controller's TCP stack.
###############################################################################

BACKFILL_REQUEST_DELAY = 1.0  # seconds between board requests during backfill

def backfill_events(db_conn_holder, since_timestamp):
    logger.info(f"Starting backfill scan for events after {since_timestamp}")

    try:
        response = board.get_event_index(board_tuple)
    except Exception as e:
        logger.error(f"Could not get event index from board: {e}")
        return

    if response is None:
        logger.error("Board returned no response for get_event_index")
        return

    current_index = response.event_index
    logger.info(f"Board current event index: {current_index}")
    events_added = 0

    for idx in range(1, current_index + 1):
        if _shutdown_requested:
            logger.info("Shutdown requested, stopping backfill.")
            break

        time.sleep(BACKFILL_REQUEST_DELAY)

        event = None
        for attempt in range(1, 4):
            try:
                event = board.get_event(board_tuple, idx)
                break
            except Exception as e:
                logger.warning(
                    f"Backfill: error fetching event {idx} "
                    f"(attempt {attempt}/3): {e}"
                )
                if attempt < 3:
                    time.sleep(2 ** attempt)

        if event is None:
            logger.error(f"Backfill: skipping event {idx} after repeated failures")
            continue

        # get_event() returns unprefixed field names: .card, .door, etc.
        if not is_valid_event(event.card, event.event_type):
            continue

        if event.timestamp and event.timestamp > since_timestamp:
            logger.info(
                f"Backfill adding: {event.timestamp}, "
                f"Door: {event.door}, Card: {event.card}"
            )
            db_insert_with_retry(
                db_conn_holder,
                event.card,
                event.door,
                event.access_granted,
                event.event_type,
                event.timestamp,
            )
            events_added += 1

    logger.info(f"Backfill complete. Added {events_added} events.")

###############################################################################
# Push-based event listener callback
#
# board.listen() is a blocking call that invokes this callback each time the
# board pushes an event notification. No polling loop; no index scanning.
# Events from listen() use event_*-prefixed field names (event.event_card,
# event.event_door, etc.) unlike the get_event() object.
###############################################################################

def make_event_handler(db_conn_holder):
    def on_event(event):
        if event is None:
            return

        card = event.event_card
        door = event.event_door
        access_granted = event.event_access_granted
        event_type = event.event_type
        timestamp = event.event_timestamp

        if not is_valid_event(card, event_type):
            return

        if timestamp is None:
            return

        logger.info(
            f"Live event: {timestamp}, Door: {door}, "
            f"Card: {card}, Granted: {access_granted}"
        )
        db_insert_with_retry(
            db_conn_holder, card, door, access_granted, event_type, timestamp
        )

    return on_event

###############################################################################
# Main
###############################################################################

def main():
    logger.info("Starting rfid2db (push-based event listener)...")
    logger.info(f"Board: serial={BOARD_SERIAL}, ip={BOARD_IP}, port={BOARD_PORT}")

    # Verify board connectivity before doing anything else.
    for attempt in range(1, 6):
        try:
            info = board.get_controller(board_tuple)
            pprint(info.__dict__, indent=2, width=1)
            break
        except Exception as e:
            logger.warning(f"Board connection attempt {attempt}/5: {e}")
            if attempt == 5:
                logger.error("Cannot connect to board. Exiting.")
                sys.exit(1)
            time.sleep(2 ** attempt)

    # Determine this machine's IP so the board knows where to push events.
    local_ip = get_local_ip()
    logger.info(f"Local IP for event listener: {local_ip}")

    # Tell the board to push events to us.
    # interval=0 means push only on real events, not on a fixed timer.
    # The board may not always return a SetListenerResponse (firmware quirk),
    # so timeouts are non-fatal: if the board was configured on a previous run
    # it will continue sending events to this IP and listen() will still work.
    listener_configured = False
    for attempt in range(1, 4):
        try:
            board.set_listener(board_tuple, ipaddress.IPv4Address(local_ip), BOARD_PORT,
                               interval=0, timeout=5.0)
            logger.info(f"Board event listener configured: {local_ip}:{BOARD_PORT}")
            listener_configured = True
            break
        except Exception as e:
            logger.warning(
                f"set_listener attempt {attempt}/3 failed: {e}"
            )
            if attempt < 3:
                time.sleep(2 ** attempt)
    if not listener_configured:
        logger.warning(
            "Could not confirm listener configuration with the board. "
            "Proceeding anyway — if the board was configured previously, "
            "push events will still be received."
        )

    # Enable door open/close/unlock special events so we receive them too.
    try:
        board.record_special_events(board_tuple, True)
        logger.info("Special event recording enabled.")
    except Exception as e:
        logger.warning(f"Could not enable special events (non-fatal): {e}")

    # Open DB connection.
    try:
        conn = get_db_connection()
        logger.info("Database connection established.")
    except Exception as e:
        logger.error(f"Cannot connect to database: {e}")
        sys.exit(1)

    db_conn_holder = [conn]

    '''
    GONNA SKIP THE BACKFILL FOR NOW TO GET THE PUSH-BASED LISTENER UP AND RUNNING, 
    THEN COME BACK AND TEST THE BACKFILL SEPARATELY. THIS WAY WE CAN START GETTING LIVE 
    EVENTS INTO THE DB SOONER, AND WE CAN ITERATE ON THE BACKFILL LOGIC WITHOUT 
    INTERRUPTING THE LIVE FEED.
    # Backfill any events that occurred while the service was not running.
    last_timestamp = get_last_rfid_event_timestamp(db_conn_holder[0])
    if last_timestamp:
        logger.info(f"Last DB event: {last_timestamp}. Running backfill...")
        backfill_events(db_conn_holder, last_timestamp)
    else:
        logger.info("No previous DB events. Backfilling from 2018-01-01...")
        backfill_events(db_conn_holder, datetime.datetime(2018, 1, 1))

    if _shutdown_requested:
        logger.info("Shutdown requested during backfill.")
        db_conn_holder[0].close()
        sys.exit(0)

    logger.info("Backfill complete. Starting push-based event listener...")
    '''
    
    on_event = make_event_handler(db_conn_holder)

    try:
        # Blocking call — returns only when interrupted.
        board.listen(on_event)
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error(f"Listener exited with error: {e}")
    finally:
        try:
            db_conn_holder[0].close()
        except Exception:
            pass
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
