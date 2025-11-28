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
    config["db_user"] = os.environ["DB_USER"]
    config["db_password"] = os.environ["DB_PASSWORD"]

    config["keyclock_url"] = os.environ["KEYCLOAK_URL"]
    config["realm_name"] = os.environ["REALM_NAME"]
    config["client_id"] = os.environ["CLIENT_ID"]
    config["client_secret"] = os.environ["CLIENT_SECRET"]

    config["user_name"] = os.environ["USER_NAME"]
    config["passcode"] = os.environ["PASSCODE"]

    config["aws_access_key"] = os.environ["AWS_ACCESS_KEY"]
    config["aws_secret_key"] = os.environ["AWS_SECRET_KEY"]
    config["aws_region"] = os.environ["AWS_REGION"]

    # Email / OTP configuration (optional, defaults keep existing behaviour)
    config["email_provider"] = os.environ.get("EMAIL_PROVIDER", "smtp").lower()

    # SMTP settings
    config["smtp_server"] = os.environ.get("SMTP_SERVER", "")
    config["smtp_port"] = int(os.environ.get("SMTP_PORT", "587"))
    config["smtp_username"] = os.environ.get("SMTP_USERNAME", "")
    config["smtp_password"] = os.environ.get("SMTP_PASSWORD", "")
    config["smtp_from_email"] = os.environ.get("SMTP_FROM_EMAIL", "")

    # AWS SES fallback (kept for future use)
    config["ses_from_email"] = os.environ.get("SES_FROM_EMAIL", os.environ.get("SMTP_FROM_EMAIL", "no-reply@yourdomain.com"))

    config = dotdict(config)

print(config)
