from typing import Dict, List, Any, Optional

from dhs_logging import logger

# This class is responsible for handling email templates, including fetching 
# required parameters from the database and building parameter dictionaries 
# for email generation.
# Split this out into its own file to keep main.py from getting too long. :)
class EmailTemplateHandler:
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def get_template_parameters(self, template_name: str) -> List[str]:
        logger.info(f"Getting template parameters for template '{template_name}' from the database...")
        
        # Get list of required parameters for a template.
        with self.conn as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT     etp.PARAMETER_name, 
                            etp.parameter_type, 
                            etp.is_required, 
                            etp.default_value
                FROM       email_template_parameters etp 
                INNER JOIN email_templates et ON et.id = etp.template_id
                WHERE      et.name = %s
                """, (template_name,))
                result = cursor.fetchall()
                
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
            
            logger.info(f"Template '{template_name}' parameters: {parameters}")
            return parameters
    
    # This is what the main code will call to extract only the needed parameters 
    # from JSON data.
    def build_template_parameters(
        self, 
        template_name: str, 
        data: Dict[str, Any]) -> Dict[str, Any]:
        # Extract only the needed parameters from JSON data.
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
            logger.error(f"Missing required parameters: {missing}")
            raise ValueError(f"Missing required parameters: {missing}")
        
        return extracted
    