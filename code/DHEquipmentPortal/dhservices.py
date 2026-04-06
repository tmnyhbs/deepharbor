"""
HTTP client for Deep Harbor services.
Provides authenticated access to both DHService (member management)
and DHEquipment (equipment management) APIs.
"""

import requests
from config import config
from dhs_logging import logger

###############################################################################
# DHService (member management) configuration
###############################################################################

DH_API_BASE_URL = config.get("dh_services", "api_base_url", fallback="http://localhost/dh/service")
DH_CLIENT_ID = config.get("dh_services", "client_name", fallback="dev-equipment-portal")
DH_CLIENT_SECRET = config.get("dh_services", "client_secret", fallback="secret")

###############################################################################
# DHEquipment configuration
###############################################################################

EQUIP_API_BASE_URL = config.get("dh_equipment", "api_base_url", fallback="http://localhost/dh/equipment")
EQUIP_CLIENT_ID = config.get("dh_equipment", "client_name", fallback="dev-equipment-portal")
EQUIP_CLIENT_SECRET = config.get("dh_equipment", "client_secret", fallback="secret")

###############################################################################
# Token management
###############################################################################

_tokens = {}  # Cache tokens by base_url


def get_access_token(client_id: str, client_secret: str, base_url: str = None) -> str:
    """Get an OAuth2 access token from a DH service."""
    url = base_url or DH_API_BASE_URL
    cache_key = url
    if cache_key in _tokens:
        return _tokens[cache_key]

    response = requests.post(
        f"{url}/token",
        data={"username": client_id, "password": client_secret},
        timeout=10,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    _tokens[cache_key] = token
    return token


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _member_headers(token: str, member_id: int = None, permissions: dict = None, role: str = None) -> dict:
    """Build headers with auth + member context for DHEquipment API calls."""
    import json
    headers = _auth_headers(token)
    if member_id:
        headers["X-Member-ID"] = str(member_id)
    if permissions:
        headers["X-Member-Permissions"] = json.dumps(permissions)
    if role:
        headers["X-Member-Role"] = role
    return headers


###############################################################################
# DHService — Member Management API
###############################################################################

def get_member_id(access_token: str, email_address: str):
    url = f"{DH_API_BASE_URL}/v1/member/id"
    response = requests.get(url, headers=_auth_headers(access_token),
                            params={"email_address": email_address}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_member_roles(access_token: str, member_id: str):
    url = f"{DH_API_BASE_URL}/v1/member/roles/"
    response = requests.get(url, headers=_auth_headers(access_token),
                            params={"member_id": member_id}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_member_identity(access_token: str, member_id: str):
    url = f"{DH_API_BASE_URL}/v1/member/identity/"
    response = requests.get(url, headers=_auth_headers(access_token),
                            params={"member_id": member_id}, timeout=10)
    response.raise_for_status()
    return response.json()


def log_user_activity(access_token: str, member_id: str, activity_data: dict):
    url = f"{DH_API_BASE_URL}/v1/dh/user_activity/"
    response = requests.post(url, headers=_auth_headers(access_token),
                             params={"member_id": member_id},
                             json=activity_data, timeout=10)
    response.raise_for_status()
    return response.json()


###############################################################################
# DHEquipment — Equipment Management API
# All calls include member context headers for permission checking.
###############################################################################

def _equip_token():
    """Get a cached token for the equipment service."""
    return get_access_token(EQUIP_CLIENT_ID, EQUIP_CLIENT_SECRET, EQUIP_API_BASE_URL)


def _equip_get(path: str, member_id: int = None, permissions: dict = None,
               role: str = None, params: dict = None):
    token = _equip_token()
    headers = _member_headers(token, member_id, permissions, role)
    response = requests.get(f"{EQUIP_API_BASE_URL}{path}",
                            headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _equip_post(path: str, data: dict, member_id: int = None,
                permissions: dict = None, role: str = None):
    token = _equip_token()
    headers = _member_headers(token, member_id, permissions, role)
    response = requests.post(f"{EQUIP_API_BASE_URL}{path}",
                             headers=headers, json=data, timeout=15)
    response.raise_for_status()
    return response.json()


def _equip_patch(path: str, data: dict, member_id: int = None,
                 permissions: dict = None, role: str = None):
    token = _equip_token()
    headers = _member_headers(token, member_id, permissions, role)
    response = requests.patch(f"{EQUIP_API_BASE_URL}{path}",
                              headers=headers, json=data, timeout=15)
    response.raise_for_status()
    return response.json()


def _equip_put(path: str, data: dict, member_id: int = None,
               permissions: dict = None, role: str = None):
    token = _equip_token()
    headers = _member_headers(token, member_id, permissions, role)
    response = requests.put(f"{EQUIP_API_BASE_URL}{path}",
                            headers=headers, json=data, timeout=15)
    response.raise_for_status()
    return response.json()


def _equip_delete(path: str, member_id: int = None,
                  permissions: dict = None, role: str = None):
    token = _equip_token()
    headers = _member_headers(token, member_id, permissions, role)
    response = requests.delete(f"{EQUIP_API_BASE_URL}{path}",
                               headers=headers, timeout=15)
    response.raise_for_status()


# ── Convenience methods ──

def get_areas(member_id=None, permissions=None, role=None):
    return _equip_get("/v1/equipment/areas", member_id, permissions, role)

def get_equipment(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/items", member_id, permissions, role, params=params)

def get_tickets(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/tickets", member_id, permissions, role, params=params)

def get_dashboard_stats(member_id=None, permissions=None, role=None):
    return _equip_get("/v1/equipment/dashboard/stats", member_id, permissions, role)

def get_groups(member_id=None, permissions=None, role=None):
    return _equip_get("/v1/equipment/groups", member_id, permissions, role)

def get_schedules(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/schedules", member_id, permissions, role, params=params)

def get_auth_sessions(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/auth-sessions", member_id, permissions, role, params=params)

def get_maintenance_schedules(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/maintenance/schedules", member_id, permissions, role, params=params)

def get_maintenance_events(member_id=None, permissions=None, role=None, **params):
    return _equip_get("/v1/equipment/maintenance/events", member_id, permissions, role, params=params)

def get_config(key: str, member_id=None, permissions=None, role=None):
    return _equip_get(f"/v1/equipment/config/{key}", member_id, permissions, role)
