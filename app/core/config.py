""" Configurations Module"""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(dotenv_path=find_dotenv())


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


config = {}

if not config:
    config["db_url"] = os.environ["DB_URL"]
    config["db_name"] = os.environ["DB_NAME"]

    config["keyclock_url"] = os.environ["KEYCLOAK_URL"]
    config["realm_name"] = os.environ["REALM_NAME"]
    config["client_id"] = os.environ["CLIENT_ID"]
    config["client_secret"] = os.environ["CLIENT_SECRET"]

    config["user_name"] = os.environ["USER_NAME"]
    config["passcode"] = os.environ["PASSCODE"]

    config = dotdict(config)

print(config)
