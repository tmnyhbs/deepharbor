import configparser
import os

###############################################################################
# Configuration
###############################################################################

# create a new configuration parser
config = configparser.ConfigParser()
config.read("config.ini")

### Environment variable overrides
# Allow environment variables to take precedence over config.ini values,
# handy for running in Docker with bridge networking where the gateway
# hostname is different from localhost
if os.environ.get("DH_API_BASE_URL"):
    if not config.has_section("dh_services"):
        config.add_section("dh_services")
    config.set("dh_services", "api_base_url", os.environ["DH_API_BASE_URL"])
