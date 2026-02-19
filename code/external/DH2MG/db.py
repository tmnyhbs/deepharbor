import psycopg2
from contextlib import contextmanager
import json

from config import config
from dhs_logging import logger
from models import Client

###############################################################################
# Database Connection Context Manager
###############################################################################

@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup."""
    schema = config["Database"]["schema"]
    conn = psycopg2.connect(
        dbname=config["Database"]["name"],
        user=config["Database"]["user"],
        password=config["Database"]["password"],
        host=config["Database"]["host"],
        options=f"-c search_path=dbo,{schema}",
    )
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


###############################################################################
# Oauth2 Functions
###############################################################################

def get_client_by_client_name(client_name: str) -> Client | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT client_name, client_secret, client_description 
                   FROM oauth2_users WHERE client_name = %s""",
                (client_name,),
            )
            client = cur.fetchone()
    if client is None:
        return None
    return Client(
        client_name=client[0],
        description=client[2],
        enabled=False,
        hashed_password=client[1],
    )
