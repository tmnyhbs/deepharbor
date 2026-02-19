from datetime import timedelta
import json
import os
from urllib.request import Request
import requests
from typing import Annotated

from fastapi import Depends, Request, Header
# Our fastapi app
from fastapiapp import app

# Our oauth2 services
import auth

from config import config
from dhs_logging import logger

# Type alias for authenticated client dependency
AuthenticatedClient = Annotated[auth.Client, Depends(auth.get_current_active_client)]

###############################################################################
# Healthcheck endpoint
###############################################################################

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": os.getenv("SERVICE_NAME", "DH_SERVICE")}

###############################################################################
# Our endpoints for oauth2
###############################################################################

# This is the token endpoint for oauth2
@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[auth.OAuth2PasswordRequestForm, auth.Depends()],
) -> auth.Token:
    logger.debug("Getting a token...")
    client = auth.authenticate_client(form_data.username, form_data.password)
    if not client:
        raise auth.HTTPException(
            status_code=auth.status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect client name or client secret",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": client.client_name}, expires_delta=access_token_expires
    )
    return auth.Token(access_token=access_token, token_type="bearer")

# This endpoint is to reauthenticate and get a new token
@app.post("/reauthenticate")
async def reauthenticate(
    current_client: auth.Client = Depends(auth.get_current_active_client),
) -> auth.Token:
    logger.debug("Reauthenticating client %s", current_client.client_name)
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": current_client.client_name}, expires_delta=access_token_expires
    )
    return auth.Token(access_token=access_token, token_type="bearer")
    
###############################################################################
# Mailgun configuration
###############################################################################

MAILGUN_API_KEY = config['mailgun']['api_key']


###############################################################################
# Mailgun functions
###############################################################################

# This function sends an email directly via the Mailgun API. 
def send_direct_email(to_email, subject, body):
    logger.info(f"Sending email to {to_email} with subject '{subject}'")
    
    response = requests.post(
        config['mailgun']['url'],
        auth=("api", MAILGUN_API_KEY),
        data={"from": f"{config['mailgun']['from_name']} <{config['mailgun']['from_email']}>",
              "to": [to_email],
              "subject": subject,
              "html": body})
    
    if response.status_code == 200:
        logger.info(f"Email sent successfully to {to_email}")
    else:
        logger.error(f"Failed to send email to {to_email}. Status code: {response.status_code}, Response: {response.text}")

    return response.status_code == 200, response.text    

# This function sends an email using a Mailgun template. The template should be set up in Mailgun 
# with the appropriate variables.
def send_template_email(to_email, subject, template_name, variables):
	return requests.post(
		config['mailgun']['url'],
        auth=("api", MAILGUN_API_KEY),
		data={"from": f"{config['mailgun']['from_name']} <{config['mailgun']['from_email']}>",
			"to": to_email,
			"subject": subject,
			"template": template_name,
			"h:X-Mailgun-Variables": json.dumps(variables)})
 

###############################################################################
# Our email endpoints
###############################################################################

@app.post("/send_email/")
async def send_email(
    current_client: AuthenticatedClient,
    request: Request,
):
    """ Send an email using the Mailgun API. The request body should contain the following fields:
        - to_email: The email address to send the email to
        - subject: The subject of the email
        - body: The HTML body of the email
    """
    data = await request.json()    
    logger.debug(f"In send_email with {data}")
    success, response_text = send_direct_email(data.get("to_email"), data.get("subject"), data.get("body"))
    if success:
        return {"status": "success", "message": f"Email sent to {data.get('to_email')} with subject '{data.get('subject')}'"}
    else:
        return {"status": "error", "message": f"Failed to send email to {data.get('to_email')}. Response: {response_text}"}

@app.post("/send_template_email/")
async def send_template_email_endpoint(
    current_client: AuthenticatedClient,
    request: Request,
):
    """ Send an email using a Mailgun template. The request body should contain the following fields:
        - to_email: The email address to send the email to
        - subject: The subject of the email
        - template: The name of the Mailgun template to use
        - variables: A dictionary of variables to pass to the Mailgun template
            The variables will be passed as a JSON string in the "h:X-Mailgun-Variables" header, 
            so they should be simple key-value pairs. For example, if you have a template 
            that has a variable called "first_name", then you could pass 
            {"first_name": "Zesty"} in the variables field, and then in the Mailgun 
            template you could use {{first_name}} to insert the value "Zesty" 
            into the email.
    """
    data = await request.json()    
    logger.debug(f"In send_template_email with {data}")
    response = send_template_email(data.get("to_email"), data.get("subject"), data.get("template"), data.get("variables"))
    if response.status_code == 200:
        return {"status": "success", "message": f"Template email sent to {data.get('to_email')} with subject '{data.get('subject')}'"}
    else:
        return {"status": "error", "message": f"Failed to send template email to {data.get('to_email')}. Status code: {response.status_code}, Response: {response.text}"} 