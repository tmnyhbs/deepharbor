#!/usr/bin/env python3

import requests
import psycopg2
import json
from typing import Dict, List, Any, Optional

class EmailTemplateHandler:
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def get_template_parameters(self, template_name: str) -> List[str]:
        print(f"Getting template parameters for template '{template_name}' from the database...")
        """Get list of required parameters for a template."""
        with self.conn.cursor() as cur:
            cur.execute("""
               SELECT     etp.PARAMETER_name, 
                          etp.parameter_type, 
                          etp.is_required, 
                          etp.default_value
               FROM       email_template_parameters etp 
               INNER JOIN email_templates et ON et.id = etp.template_id
               WHERE      et.name = %s
            """, (template_name,))
            result = cur.fetchall()
            
            if not result:
                return []
            
            # Return the results as a list
            parameters = []
            for row in result:
                parameters.append({
                    "name": row[0],
                    "type": row[1],
                    "required": row[2],
                    "default_value": row[3]
                })
            
            print(f"Template '{template_name}' parameters: {parameters}")
            return parameters
    
    def build_template_parameters(
        self, 
        template_name: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract only the needed parameters from JSON data."""
        required_params = self.get_template_parameters(template_name)
        
        # Extract only the fields that the template needs
        extracted = {}
        missing = []
        
        for param in required_params:
            param_name = param['name']
            if param_name in data:
                extracted[param_name] = data[param_name]
            else:
                missing.append(param_name)
        
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")
        
        return extracted
    

# Replace with your actual URL
#BASE_URL = "http://localhost:9000/" # For local testing
BASE_URL = "http://localhost/dh/email" # For testing with Docker Compose

def get_access_token(username: str, password: str) -> str:
    url = f"{BASE_URL}/token"
    response = requests.post(url, data={"username": username, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]

if __name__ == "__main__":
     # Connect to database
    conn = psycopg2.connect(
        dbname="deepharbor",
        user="dh",
        password="dh",
        host="localhost"
    )
    
    handler = EmailTemplateHandler(conn)
    
    incoming_data = {
        "first_name": "Zesty",
        "last_name": "Zest",
        "email_address": "tachoknight@gmail.com",
        "nickname": "ZestyZest",
        "member_id": "12345",
    }
    
    template_params = {}
    try:
        template_params = handler.build_template_parameters(
            "dh-happy-trails-to-you", 
            incoming_data
        )
        print(f"Extracted parameters: {template_params}")
        # Result: {"user_name": "John Doe", "order_id": "ORD-12345", "total_amount": 99.99}
        
    except ValueError as e:
        print(f"Error: {e}")
    
    conn.close()
    
    
    username = "dev-mail-client"
    password = "Ux8XY-I4FwIonu6LIxx9F0F-Lw_OrXsKcIG5YPT9nW8"

    # Get access token
    print("Getting access token...")
    access_token = get_access_token(username, password)
    print(f"Access Token: {access_token}")
    '''
    # Create a new email message for testing
    email_message = {
        "to_email": "tachoknight@gmail.com",
        "subject": "Test Email from DH2MG",
        "body": "<h2>Oh hey, here's an email sent from the DH2MG service.</h2><br/><p>This is just a test email to verify that the email sending functionality is working correctly.</p>"
    }
    
    url = f"{BASE_URL}/send_email/"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=email_message)
    response.raise_for_status()
    email_response = response.json()
    print(f"Email Response: {email_response}")
    '''
    
    # Now let's try a template
    '''
    template_email_message = {
        "to_email": "tachoknight@gmail.com",
        "subject": "Hmm test Template Email from DH2MG",
        "template": "dh-welcome-to-ps1",
        "variables": {
            "first_name": "Zesty"
        }
    }
    '''
    
    '''
    template_email_message = {
        "to_email": "tachoknight@gmail.com",
        "subject": "Welcome to ps1",
        "template": "dh-you-are-now-a-member",
        "variables": {
            "first_name": "Zesty"
        }
    }
    '''
    
    template_email_message = {
        "to_email": "tachoknight@gmail.com",
        "subject": "Awwwww bye",
        "template": "dh-happy-trails-to-you",
        "variables": template_params
    }

    url = f"{BASE_URL}/send_template_email/"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=template_email_message)
    response.raise_for_status()
    template_email_response = response.json()
    print(f"Template Email Response: {template_email_response}")

