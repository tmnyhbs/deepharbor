import uuid
import requests
import json
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
import msal

# Our stuff
import dhservices
from dhs_logging import logger
import app_config
from config import config

### Dev mode flag — read from app_config so we only check the env var once
AUTH_MODE = app_config.AUTH_MODE
DEV_BANNER = app_config.DEV_BANNER
if AUTH_MODE == "dev":
    logger.info("AUTH_MODE=dev — B2C authentication bypassed, dev login enabled")

app = Flask(__name__)
app.config.from_object(app_config)
Session(app)
csrf = CSRFProtect(app)

from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f"CSRF validation failed: {e.description}")
    if request.is_json or request.content_type == 'application/json':
        return {"error": "CSRF token missing or invalid"}, 400
    flash('Your session has expired or this form submission was invalid. Please try again.', 'error')
    return redirect(request.referrer or url_for('index'))

###############################################################################
# Health check endpoint
###############################################################################

@app.route("/health")
def health():
    return "OK", 200

@app.route("/version")
def version():
    return {"version": config["git"]["version"]}, 200

###############################################################################
# Flask routes for B2C flows, including login and logout
###############################################################################

@app.route("/anonymous")
def anonymous():
    logger.info("Anonymous route accessed")
    return "anonymous page"

@app.route("/")
def index():
    logger.info("Main route accessed")
    
    if not session.get("user"):
        if AUTH_MODE == "dev":
            return redirect(url_for("dev_login"))
        logger.info("No user logged in, building auth code flow")
        session["flow"] = _build_auth_code_flow(scopes=app_config.SCOPE)
        return render_template(
            "index.html", auth_url=session["flow"]["auth_uri"], version=msal.__version__
        )
    else:
        logger.info("User logged in, rendering index with user info")
        
        # Always fetch fresh user roles and permissions to ensure they're up-to-date
        try:
            # Get access token for DHService
            access_token = dhservices.get_access_token(
                dhservices.DH_CLIENT_ID, 
                dhservices.DH_CLIENT_SECRET
            )
            
            # Get member ID from email
            user_email = session["user"].get("email") or session["user"].get("preferred_username")
            member_data = dhservices.get_member_id(access_token, user_email)
            member_id = member_data.get("member_id")
            
            if member_id:
                # Get member roles
                roles_data = dhservices.get_member_roles(access_token, str(member_id))
                
                # Extract role name and permissions
                if roles_data and "roles" in roles_data and len(roles_data["roles"]) > 0:
                    role_info = roles_data["roles"][0]  # Get first role
                    session["user_role"] = role_info.get("role_name", "Unknown")
                    session["user_permissions"] = role_info.get("permission", {})
                    logger.info(f"Loaded permissions for {user_email}: {session['user_permissions']}")
                else:
                    session["user_role"] = "No Role"
                    session["user_permissions"] = {}
            else:
                session["user_role"] = "Unknown"
                session["user_permissions"] = {}
                
        except Exception as e:
            logger.error(f"Error fetching user roles: {e}")
            session["user_role"] = "Error"
            session["user_permissions"] = {}
        
        return render_template(
            "index.html",
            user=session["user"],
            user_role=session.get("user_role", "Unknown"),
            user_permissions=session.get("user_permissions", {}),
            version=msal.__version__
        )

@app.route("/login")
def login():
    if AUTH_MODE == "dev":
        return redirect(url_for("dev_login"))
    print("Login route accessed")
    # Technically we could use empty list [] as scopes to do just sign in,
    # here we choose to also collect end user consent upfront
    session["flow"] = _build_auth_code_flow(scopes=app_config.SCOPE)
    return render_template(
        "login.html", auth_url=session["flow"]["auth_uri"], version=msal.__version__
    )

@app.route(app_config.REDIRECT_PATH)  # Its absolute URL must match your app's redirect_uri set in B2C
def authorized():
    logger.info("Authorized route accessed")
    try:
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_auth_code_flow(
            session.get("flow", {}), request.args
        )
        if "error" in result:
            return render_template("auth_error.html", result=result)
        
        user_claims = result.get("id_token_claims")
        
        # Check if user has roles before allowing login
        try:
            # Get access token for DHService
            access_token = dhservices.get_access_token(
                dhservices.DH_CLIENT_ID, 
                dhservices.DH_CLIENT_SECRET
            )
            
            # Get member ID from email
            user_email = user_claims.get("email") or user_claims.get("preferred_username")
            if not user_email:
                logger.error("No email found in user claims")
                return render_template("auth_error.html", result={
                    "error": "Authorization Failed",
                    "error_description": "Unable to verify your account. No email address found."
                })
            
            member_data = dhservices.get_member_id(access_token, user_email)
            member_id = member_data.get("member_id")
            
            if not member_id:
                logger.warning(f"No member_id found for email: {user_email}")
                return render_template("auth_error.html", result={
                    "error": "Authorization Failed",
                    "error_description": "You are not authorized to access this application. Your account is not registered in the system."
                })
            
            # Get member roles
            roles_data = dhservices.get_member_roles(access_token, str(member_id))
            
            # Check if user has any roles
            if not roles_data or "roles" not in roles_data or len(roles_data["roles"]) == 0:
                logger.warning(f"No roles assigned to member_id: {member_id}, email: {user_email}")
                return render_template("auth_error.html", result={
                    "error": "Authorization Failed",
                    "error_description": "You are not authorized to access this application. No administrative roles have been assigned to your account. Please contact an administrator for access."
                })
            
            # User has roles, allow login
            logger.info(f"User {user_email} authorized with roles: {roles_data['roles']}")
            session["user"] = user_claims
            _save_cache(cache)
            
            # Log login activity
            try:
                dhservices.log_user_activity(
                    access_token,
                    str(member_id),
                    {
                        "activity_details": {
                            "action": "login",
                            "email": user_email,
                            "roles": roles_data.get('roles', [])
                        }
                    }
                )
            except Exception as log_error:
                logger.error(f"Failed to log login activity: {log_error}")
            
        except Exception as e:
            logger.error(f"Error checking user roles during authorization: {e}")
            return render_template("auth_error.html", result={
                "error": "Authorization Error",
                "error_description": f"An error occurred while verifying your account: {str(e)}"
            })
            
    except ValueError:  # Usually caused by CSRF
        pass  # Simply ignore them
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    logger.info("Logout route accessed")
    
    # Log logout activity before clearing session
    if session.get("user"):
        try:
            access_token = dhservices.get_access_token(
                dhservices.DH_CLIENT_ID,
                dhservices.DH_CLIENT_SECRET
            )
            user_email = session["user"].get("email") or session["user"].get("preferred_username")
            if user_email:
                member_data = dhservices.get_member_id(access_token, user_email)
                member_id = member_data.get("member_id")
                if member_id:
                    dhservices.log_user_activity(
                        access_token,
                        str(member_id),
                        {
                            "activity_details": {
                                "action": "logout",
                                "email": user_email
                            }
                        }
                    )
        except Exception as log_error:
            logger.error(f"Failed to log logout activity: {log_error}")
    
    session.clear()  # Wipe out user and its token cache from session

    if AUTH_MODE == "dev":
        # Dev mode — just redirect to index, no B2C logout needed
        response = redirect(url_for("index"))
    else:
        response = redirect(  # Also logout from your tenant's web session
            app_config.AUTHORITY
            + "/oauth2/v2.0/logout"
            + "?post_logout_redirect_uri="
            + url_for("index", _external=True)
        )

    return response

@app.route("/graphcall")
def graphcall():
    logger.info("Graphcall route accessed")
    token = _get_token_from_cache(app_config.SCOPE)
    if not token:
        return redirect(url_for("login"))
    graph_data = requests.get(  # Use token to call downstream service
        app_config.ENDPOINT,
        headers={"Authorization": "Bearer " + token["access_token"]},
    ).json()
    return render_template("graph.html", result=graph_data)

def _load_cache():
    logger.info("Loading token cache")
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    logger.info("Saving token cache")
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def _build_msal_app(cache=None, authority=None):
    logger.info("Building MSAL app")
    return msal.ConfidentialClientApplication(
        app_config.CLIENT_ID,
        authority=authority or app_config.AUTHORITY,
        client_credential=app_config.CLIENT_SECRET,
        token_cache=cache,
    )

def _build_auth_code_flow(authority=None, scopes=None):
    logger.info("Building auth code flow")
    return _build_msal_app(authority=authority).initiate_auth_code_flow(
        scopes or [], redirect_uri=url_for("authorized", _external=True)
    )

def _get_token_from_cache(scope=None):
    logger.debug("Getting token from cache")
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:  # So all account(s) belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result

app.jinja_env.globals.update(_build_auth_code_flow=_build_auth_code_flow)  # Used in template
app.jinja_env.globals.update(git_version=config.get("git", "version", fallback="unknown"))  # Used in footer
app.jinja_env.globals.update(now=datetime.now)  # Used in footer for dynamic year
app.jinja_env.globals.update(auth_mode=AUTH_MODE)  # Used in dev login routes
app.jinja_env.globals.update(dev_banner=DEV_BANNER)  # Used in dev banner


###############################################################################
# Permission checking decorator for admin API endpoints
###############################################################################

def requires_change_permission(tab_name):
    """Check that the logged-in user has 'change' permission for the given tab."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user"):
                return {"error": "Not authenticated"}, 401
            permissions = session.get("user_permissions", {})
            change_perms = permissions.get("change", [])
            if "all" not in change_perms and tab_name not in change_perms:
                user_email = session["user"].get("email") or session["user"].get("preferred_username")
                logger.warning(
                    f"Permission denied: {user_email} attempted to change '{tab_name}'"
                )
                return {"error": "Permission denied"}, 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_view_permission(tab_name):
    """Check that the logged-in user has 'view' or 'change' permission for the given tab."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user"):
                return {"error": "Not authenticated"}, 401
            permissions = session.get("user_permissions", {})
            view_perms = permissions.get("view", [])
            change_perms = permissions.get("change", [])
            if ("all" not in view_perms and tab_name not in view_perms and
                    "all" not in change_perms and tab_name not in change_perms):
                user_email = session["user"].get("email") or session["user"].get("preferred_username")
                logger.warning(
                    f"Permission denied: {user_email} attempted to view '{tab_name}'"
                )
                return {"error": "Permission denied"}, 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


###############################################################################
# Dev mode login routes — only active when AUTH_MODE=dev
# These replace the B2C authentication flow with a simple user picker
# that lets developers quickly log in as preset seed-data users.
# Authorization (role/permission checks) still works normally.
###############################################################################

# Preset users for the dev login page. These match the seed data in
# pg/sql/seed_data.sql — don't change the IDs without updating the SQL.
ADMIN_DEV_USERS = [
    {"member_id": 1, "name": "Ada Lovelace", "email": "ada.lovelace@example.com", "role": "Administrator"},
    {"member_id": 3, "name": "Nikola Tesla", "email": "nikola.tesla@example.com", "role": "Authorizer"},
    {"member_id": 5, "name": "Grace Hopper", "email": "grace.hopper@example.com", "role": "Board"},
]

@app.route("/dev-login")
def dev_login():
    """Show the dev login page with preset user options"""
    if AUTH_MODE != "dev":
        return redirect(url_for("index"))
    return render_template("dev_login.html", preset_users=ADMIN_DEV_USERS)

@app.route("/dev-login/select", methods=["POST"])
def dev_login_select():
    """Handle dev login — authenticate via DHService API, set session"""
    if AUTH_MODE != "dev":
        return redirect(url_for("index"))

    member_id = request.form.get("member_id")
    if not member_id:
        return redirect(url_for("dev_login"))

    try:
        # Get DHService access token — same as the B2C callback does
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID,
            dhservices.DH_CLIENT_SECRET
        )

        # Get member identity to populate session
        identity = dhservices.get_member_identity(access_token, member_id)

        # Extract email from identity
        emails = identity.get("emails", [])
        email = emails[0]["email_address"] if emails else f"dev-user-{member_id}@example.com"

        # Verify they have roles (same check the B2C callback does)
        roles_data = dhservices.get_member_roles(access_token, member_id)
        if not roles_data or "roles" not in roles_data or len(roles_data["roles"]) == 0:
            return render_template("auth_error.html", result={
                "error": "Authorization Failed",
                "error_description": f"Member ID {member_id} has no admin roles assigned. "
                    "The admin portal requires a role (Administrator, Authorizer, or Board)."
            })

        # Build a user dict that looks like what B2C id_token_claims would give us
        session["user"] = {
            "name": f"{identity.get('first_name', '')} {identity.get('last_name', '')}".strip(),
            "email": email,
            "preferred_username": email,
            "dev_mode": True,
        }

        logger.info(f"Dev login: member_id={member_id}, email={email}")

        # Log login activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(member_id),
                {
                    "activity_details": {
                        "action": "dev_login",
                        "email": email,
                        "roles": roles_data.get("roles", [])
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log dev login activity: {log_error}")

    except Exception as e:
        logger.error(f"Dev login error: {e}")
        return render_template("auth_error.html", result={
            "error": "Dev Login Error",
            "error_description": f"Failed to authenticate with DHService: {str(e)}. "
                "Make sure the database is running and seed data is loaded."
        })

    return redirect(url_for("index"))


###############################################################################
# API routes to call DHService endpoints
###############################################################################

@app.route("/api/log_activity", methods=["POST"])
def api_log_activity():
    """Log user activity (tab selections, etc.)"""
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID,
            dhservices.DH_CLIENT_SECRET
        )
        
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        # Get activity data from request
        activity_data = request.get_json()
        
        # Log the activity
        result = dhservices.log_user_activity(
            access_token,
            str(logged_in_member_id),
            {"activity_details": activity_data}
        )
        
        return result
    except Exception as e:
        logger.error(f"Error logging user activity: {e}")
        return {"error": str(e)}, 500

@app.route("/api/search")
def api_search():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    query = request.args.get("query", "")
    if not query:
        return {"error": "Query parameter required"}, 400
    
    try:
        # Get access token for DHService    
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        
        # Get logged-in user's member ID for logging
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        # Search for members
        members = dhservices.search_members(access_token, query)
        
        # Log search activity
        try:
            # Handle both dict and list responses
            if isinstance(members, dict):
                results_count = len(members.get("members", []))
            elif isinstance(members, list):
                results_count = len(members)
            else:
                results_count = 0
            
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "search",
                        "query": query,
                        "results_count": results_count
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log search activity: {log_error}")
        
        return members
    except Exception as e:
        print(f"Error searching members: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/identity")
@requires_view_permission("identity")
def api_member_identity():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        # Get access token for DHService
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        
        # Get member identity
        identity = dhservices.get_member_identity(access_token, member_id)
        return identity
    except Exception as e:
        print(f"Error getting member identity: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/roles")
@requires_view_permission("roles")
def api_member_roles():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        # Get access token for DHService
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        
        # Get member roles
        roles = dhservices.get_member_roles(access_token, member_id)
        logger.info(f"Member roles for member_id {member_id}: {roles}")
        return roles
    except Exception as e:
        print(f"Error getting member roles: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/status")
@requires_view_permission("status")
def api_member_status():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        status = dhservices.get_member_status(access_token, member_id)
        return status
    except Exception as e:
        print(f"Error getting member status: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/forms")
@requires_view_permission("forms")
def api_member_forms():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        forms = dhservices.get_member_forms(access_token, member_id)
        return forms
    except Exception as e:
        print(f"Error getting member forms: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/connections")
@requires_view_permission("connections")
def api_member_connections():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        connections = dhservices.get_member_connections(access_token, member_id)
        return connections
    except Exception as e:
        print(f"Error getting member connections: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/extras")
@requires_view_permission("extras")
def api_member_extras():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        extras = dhservices.get_member_extras(access_token, member_id)
        # They may not have any extras, so return empty dict instead of null
        if extras is None:
            extras = {}
        return extras
    except Exception as e:
        print(f"Error getting member extras: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/authorizations")
@requires_view_permission("authorizations")
def api_member_authorizations():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        authorizations = dhservices.get_member_authorizations(access_token, member_id)
        if authorizations is None:
            # They may not have any authorizations, so return empty list instead of null
            authorizations = []
        return authorizations
    except Exception as e:
        print(f"Error getting member authorizations: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/notes")
@requires_view_permission("notes")
def api_member_notes():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        notes = dhservices.get_member_notes(access_token, member_id)
        return notes
    except Exception as e:
        print(f"Error getting member notes: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/entry")
@requires_view_permission("entry")
def api_member_entry():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        entry_logs = dhservices.get_member_entry_logs(access_token, member_id)
        return entry_logs
    except Exception as e:
        print(f"Error getting member entry logs: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/access")
@requires_view_permission("access")
def api_member_access():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        access = dhservices.get_member_access(access_token, member_id)
        if access is None:
            # They may not have any access records (e.g. new member)
            # so return empty list instead of null
            access = []
        return access
    except Exception as e:
        print(f"Error getting member access: {e}")
        return {"error": str(e)}, 500

@app.route("/api/authorizations/available")
def api_available_authorizations():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        available_auths = dhservices.get_available_authorizations(access_token)
        return available_auths
    except Exception as e:
        print(f"Error getting available authorizations: {e}")
        return {"error": str(e)}, 500

@app.route("/api/membership_levels/available")
def api_available_membership_levels():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401

    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID,
            dhservices.DH_CLIENT_SECRET
        )
        levels = dhservices.get_available_membership_levels(access_token)
        return levels
    except Exception as e:
        print(f"Error getting available membership levels: {e}")
        return {"error": str(e)}, 500

# POST endpoints for updating member data
@app.route("/api/member/identity", methods=["POST"])
@requires_change_permission("identity")
def api_update_member_identity():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_identity(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_identity",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member identity: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/status", methods=["POST"])
@requires_change_permission("status")
def api_update_member_status():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_status(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_status",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member status: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/roles", methods=["POST"])
@requires_change_permission("roles")
def api_update_member_roles():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_roles(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_roles",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member roles: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/extras", methods=["POST"])
@requires_change_permission("extras")
def api_update_member_extras():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_extras(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_extras",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member extras: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/authorizations", methods=["POST"])
@requires_change_permission("authorizations")
def api_update_member_authorizations():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_authorizations(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_authorizations",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member authorizations: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/notes", methods=["POST"])
@requires_change_permission("notes")
def api_update_member_notes():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_notes(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_notes",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member notes: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/access", methods=["POST"])
@requires_change_permission("access")
def api_update_member_access():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_access(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_access",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member access: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/forms", methods=["POST"])
@requires_change_permission("forms")
def api_update_member_forms():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_forms(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_forms",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member forms: {e}")
        return {"error": str(e)}, 500

@app.route("/api/member/connections", methods=["POST"])
@requires_change_permission("connections")
def api_update_member_connections():
    if not session.get("user"):
        return {"error": "Not authenticated"}, 401
    
    member_id = request.args.get("member_id", "")
    if not member_id:
        return {"error": "member_id parameter required"}, 400
    
    try:
        access_token = dhservices.get_access_token(
            dhservices.DH_CLIENT_ID, 
            dhservices.DH_CLIENT_SECRET
        )
        # Get logged-in user's member ID
        user_email = session["user"].get("email") or session["user"].get("preferred_username")
        member_data = dhservices.get_member_id(access_token, user_email)
        logged_in_member_id = member_data.get("member_id")
        
        data = request.get_json()
        data["modified_by"] = logged_in_member_id
        result = dhservices.update_member_connections(access_token, member_id, data)
        
        # Log update activity
        try:
            dhservices.log_user_activity(
                access_token,
                str(logged_in_member_id),
                {
                    "activity_details": {
                        "action": "update_connections",
                        "target_member_id": member_id,
                        "fields_updated": list(data.keys())
                    }
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to log update activity: {log_error}")
        
        return result
    except Exception as e:
        logger.error(f"Error updating member connections: {e}")
        return {"error": str(e)}, 500