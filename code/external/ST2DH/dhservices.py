import email
import os
import requests

from dhs_logging import logger
from config import config

# This module is where we invoke the service endpoints of Deep Harbor

###############################################################################
## DHService API configuration
###############################################################################

# This is the base URL for our DHService API, with env var override
# for running in Docker with bridge networking
DH_API_BASE_URL = os.environ.get("DH_API_BASE_URL", config.get("dh_services", "api_base_url"))
# This is the client ID and secret for our DHService API
DH_CLIENT_ID = config.get("dh_services", "client_name")
DH_CLIENT_SECRET = config.get("dh_services", "client_secret")


###############################################################################
# Service functions to call Deep Harbor API endpoints
# Note that these functions are specific to dealing with the
# payment data and are a very small subset of the full DHService API. 
############################################################################### 

# Our function to get an access token from DHService using oauth2 client 
# credentials flow
def get_access_token(username: str, password: str) -> str:
    url = f"{DH_API_BASE_URL}/token"
    response = requests.post(url, data={"username": username, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]

def save_stripe_data(access_token: str, stripe_message: str):
    url = f"{DH_API_BASE_URL}/v1/payment/stripe_webhook/"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=stripe_message)
    response.raise_for_status()
    return response.json()

def get_products(access_token: str):
    url = f"{DH_API_BASE_URL}/v1/products/"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["products"]

def get_member_id(access_token: str, email_address: str):
    url = f"{DH_API_BASE_URL}/v1/member/id"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params={"email_address": email_address})
    response.raise_for_status()
    return response.json()["member_id"]

def get_notes(access_token: str, member_id: int):
    url = f"{DH_API_BASE_URL}/v1/member/notes/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"member_id": member_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["notes"]

def get_member_connections(access_token: str, member_id: str):
    url = f"{DH_API_BASE_URL}/v1/member/connections/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"member_id": member_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def get_member_status(access_token: str, member_id: str):
    url = f"{DH_API_BASE_URL}/v1/member/status/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"member_id": member_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def update_member_notes(access_token: str, member_id: str, notes_data: dict):
    url = f"{DH_API_BASE_URL}/v1/member/notes/"
    headers = {"Authorization": f"Bearer {access_token}"}
    headers["X-Member-ID"] = str(member_id)
    params = {"member_id": member_id}
    response = requests.post(url, headers=headers, params=params, json=notes_data)
    response.raise_for_status()
    return response.json()

def update_member_connections(access_token: str, member_id: str, connections_data: dict):
    url = f"{DH_API_BASE_URL}/v1/member/connections/"
    headers = {"Authorization": f"Bearer {access_token}"}
    headers["X-Member-ID"] = str(member_id)
    params = {"member_id": member_id}
    response = requests.post(url, headers=headers, params=params, json=connections_data)
    response.raise_for_status()
    return response.json()

def update_member_status(access_token: str, member_id: str, status_data: dict):
    url = f"{DH_API_BASE_URL}/v1/member/status/"
    headers = {"Authorization": f"Bearer {access_token}"}
    headers["X-Member-ID"] = str(member_id)
    params = {"member_id": member_id}
    response = requests.post(url, headers=headers, params=params, json=status_data)
    response.raise_for_status()
    return response.json()

# This function is for finding a member in our database based on their Stripe customer ID, 
# which is useful for when we get a webhook event from Stripe but we can't find an email address 
# for the customer because they deleted their account in Stripe. In that case, we can still 
# try to find them in our database based on their Stripe customer ID, and if we can find them there, 
# then we can update their membership status based on the webhook event.
def get_member_by_stripe_customer_id(access_token: str, stripe_customer_id: str):
    url = f"{DH_API_BASE_URL}/v1/member/by_stripe_customer_id/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"stripe_customer_id": stripe_customer_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()