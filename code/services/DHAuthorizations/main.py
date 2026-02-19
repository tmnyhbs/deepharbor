import json
import os
from urllib import request
import requests
import psycopg2
import psycopg2.extensions
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException

from config import config
from dhs_logging import logger

# Our FastAPI app
app = FastAPI()

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
# Database functions
###############################################################################

def get_member_identity(member_id: str) -> str:
    # Fetch the member identity json from the database based on member_id
    logger.debug(f"Fetching member identity from database for member id {member_id}")
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT identity FROM member WHERE id = %s", (member_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError(f"Member ID {member_id} not found")

def get_authorization_changes(member_id: str) -> dict:
    # Call the get_authorization_changes_for_member 
    # function in the database to get the changes
    logger.debug(
        f"Fetching authorization changes from database for member id {member_id}")
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT get_authorization_changes_for_member(%s)", (member_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError(f"Authorization changes for Member ID {member_id} not found")

def get_authorization_status(member_auths: dict) -> dict:
    # Call the get_member_authorization_status function in the database to get the status 
    # of all authorizations
    logger.debug(
        f"Fetching authorization status from database for member auths {member_auths}")
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT get_member_authorization_status(%s)", (json.dumps(member_auths),))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError(f"Authorization status for member auths {member_auths} not found")


###############################################################################
# Healthcheck endpoint
###############################################################################

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": os.getenv("SERVICE_NAME", "DH_Authorizations"),
    }


###############################################################################
# Endpoint to sync authorizations
###############################################################################

@app.post("/v1/change_authorizations")
async def change_authorizations(request: dict):
    logger.info(f"Change authorizations request received: {request}")

    def prepare_payload(username: str, request: dict, add_or_remove: str) -> dict:
        # This is a bit silly but we're going to do this work here instead
        # of making the DH2AD worker do it. DH2AD expects the json to look
        # like this:
        # {
        #     "username": "jdoe",
        #     "status": "add", # or "remove"
        #     "authorizations": ["Wood Mini Lathe", "Band Saw"]  # This is a list of group names that the user should be in
        # }
        # And we already have the full list of authorizations with their current status 
        # from the get_authorization_status function, so we just need to transform it into the 
        # format that DH2AD expects. This way we can keep the logic for determining which OUs 
        # to set or unset in Active Directory in one place (the DH2AD worker) and keep this 
        # service focused on just fetching the member identity and authorizations from the 
        # database and preparing the request for DH2AD.
        payload = {}
        for status, auths in request.items():
            for auth_type, auth_list in auths.items():
                for auth in auth_list:            
                    if status == add_or_remove:
                        payload.setdefault("authorizations", []).append(auth)
                        payload["username"] = username
                        payload["status"] = 'add' if status == "authorized" else 'remove'
        return payload
        
    # Okay, here we go...
    try:
        member_id = request.get("member_id")
        if not member_id:
            raise HTTPException(status_code=400, detail="member_id is required")
        logger.debug(f"Member ID extracted: {member_id}")

        # Now we need to get the member identity from the database
        member_identity = get_member_identity(member_id)
        logger.info(
            f"Fetched member identity: {member_identity} for member id {member_id}"
        )
        # Now get the member's active directory username (active_directory_username)
        # from the member identity JSON
        # For simplicity, let's assume member_identity is a dict with the needed info
        active_directory_username = member_identity.get("active_directory_username")
        if not active_directory_username:
            raise HTTPException(
                status_code=400,
                detail="Active Directory username not found in member identity",
            )

        logger.info(f"Active Directory username found: {active_directory_username}")

        # This is a bit of a blunt-force approach: we use the authorizations array
        # which contains the current state of all authorizations for the member, and 
        # we pass that to the get_member_authorization_status function in the database, 
        # which will return the status of all authorizations (e.g. which ones are 
        # currently authorized vs not authorized). This way we can show the full list of
        # authorizations with their current status in the DH2AD worker, which can then 
        # decide which OUs to set or unset for the user in Active Directory based on that 
        # status. This is different from the get_authorization_changes_for_member function, 
        # which only shows what has changed from the last version to the current version, 
        # and doesn't show the full list of authorizations with their current status.
        #
        # Why are we doing it this way instead of using get_authorization_changes_for_member? 
        # Because we want to avoid the possibility that changes were not processed correctly 
        # in the DH2AD worker and the member's Active Directory OUs are out of sync with their 
        # current authorizations in the database. 
        # By always sending the full list of authorizations with their current status, we can 
        # ensure that the DH2AD worker can correct any discrepancies and keep Active Directory 
        # in sync with the database.
        authorization_changes = get_authorization_status(request.get("change_data", {}))
        logger.info(
            f"Fetched authorization changes: {authorization_changes} for member id {member_id}"
        )
        
        dh2ad_request = prepare_payload(active_directory_username, 
                                        authorization_changes, 
                                        "authorized")
        logger.info(f"Prepared DH2AD request for adding authorizations: {dh2ad_request}")
        # Get DH2AD endpoint from config
        dh2ad_endpoint = config["DH2AD"]["endpoint_url"]
        logger.info(f"DH2AD endpoint URL: {dh2ad_endpoint}")
        # Send the request to DH2AD worker        
        url = dh2ad_endpoint
        payload = dh2ad_request
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logger.error(f"Failed to add authorizations via DH2AD: {response.text}")
            raise HTTPException(
                status_code=500, detail=f"Failed to add authorizations via DH2AD: {response.text}"
            )
        dh2ad_request = prepare_payload(active_directory_username, 
                                        authorization_changes, 
                                        "not_authorized")
        logger.info(f"Prepared DH2AD request for removing authorizations: {dh2ad_request}")
         # Send the request to DH2AD worker        
        url = dh2ad_endpoint
        payload = dh2ad_request
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logger.error(f"Failed to remove authorizations via DH2AD: {response.text}")
            raise HTTPException(
                status_code=500, detail=f"Failed to remove authorizations via DH2AD: {response.text}"
            )

        # And we're done! At this point, the DH2AD worker should have processed the request and made 
        # the necessary changes in Active Directory. We can return a success response to the client.
        processed_request = {"processed": True, "details": request}
        logger.info(
            f"Authorization changes processed successfully: {processed_request}"
        )
        return processed_request
    except Exception as e:
        logger.error(f"Error processing authorization changes: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
