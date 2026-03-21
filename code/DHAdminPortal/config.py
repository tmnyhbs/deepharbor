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

if os.environ.get("DH_CLIENT_ID"):
    if not config.has_section("dh_services"):
        config.add_section("dh_services")
    config.set("dh_services", "client_name", os.environ["DH_CLIENT_ID"])

if os.environ.get("DH_CLIENT_SECRET"):
    if not config.has_section("dh_services"):
        config.add_section("dh_services")
    config.set("dh_services", "client_secret", os.environ["DH_CLIENT_SECRET"])

if os.environ.get("DH_SECRET_KEY"):
    if not config.has_section("flask"):
        config.add_section("flask")
    config.set("flask", "secret_key", os.environ["DH_SECRET_KEY"])
