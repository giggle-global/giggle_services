"""
CRUD Operation for general useage
"""

import inspect
import os
import re
import string
import random
import pytz
import time

from pymongo.collection import Collection
from datetime import datetime
from pymongo.errors import PyMongoError
from fastapi import HTTPException, Request
from app.core.response import error_response_model
from app.core.db import database
from app.core.audit_log import define_logger
from app.core.constant import error_messages
from app.core.models.audit_log import OperationType, AuditLogInfoType
from app.core.constant import ROLE_ACCESS
from pymongo.collection import Collection
from cryptography.fernet import Fernet
from app.core.config import config

KEY = config["secret_key"].encode("utf-8")


def generate_id(length: int) -> str:
    """
    Generate a random ID consisting of uppercase letters and digits for primary key.
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    characters = string.digits + string.ascii_uppercase
    return "".join(random.choices(characters, k=length))


def generate_pk_id(length: int, prefix: str) -> str:
    """
    Generate a unique primary key ID for a document in a collection.

    Args:
        length (int): The length of the generated ID.
        prefix (str): The prefix to prepend to the generated ID.

    Returns:
        str: The unique primary key ID for the document.

    """

    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    if not isinstance(prefix, str):
        raise ValueError("Prefix must be a string.")
    pk_id = generate_id(length=length)
    return prefix + "_" + pk_id


def local_time_to_gmt_epoch():
    """
    Converts the current local time to GMT epoch time.

    Returns:
        int: The GMT epoch time.
    """
    # Get the current local time
    current_local_time = datetime.now()

    # Convert local time to GMT (UTC)
    gmt_timezone = pytz.timezone("UTC")
    current_gmt_time = current_local_time.astimezone(gmt_timezone)

    epoch = datetime(1970, 1, 1, tzinfo=pytz.utc)
    diff = current_gmt_time - epoch
    return int(diff.total_seconds())


def validate_whitespace_or_none(value):
    """
    Validates whether a value is whitespace or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if value is None or value.isspace() or value == "":
        error_response = error_response_model(code=422, error_code=1003)
        define_logger(
            level=30,
            request=None,
            user=None,
            loggName=loggername,
            pid=pid,
            message=error_messages[1003],
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value


def validate_email(value):
    """
    Validates whether a value is an email or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if not value:
        return None
    if value and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
        error_response = error_response_model(code=422, error_code=1004)
        define_logger(
            level=30, loggName=loggername, pid=pid, message=error_messages[1004]
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value


def validate_alphabets(value):
    """
    Validates whether a value is alphabets or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if value and not re.match(r"^[a-zA-Z ]+$", value):
        error_response = error_response_model(code=422, error_code=1005)
        define_logger(
            level=30, loggName=loggername, pid=pid, message=error_messages[1005]
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value


def check_user_access(
    function_name: str,
    role: list,
    request: Request = None,
    user: dict = None,
):
    """
    Function to check the authorization of the user.
    """
    loggername = inspect.stack()[0]
    pid = os.getpid()
    if role:
        # Check if the roles are not empty
        if not ROLE_ACCESS:
            error_response = error_response_model(code=403, error_code=7000)
            define_logger(
                level=30,
                request=request,
                user=user,
                loggName=loggername,
                pid=pid,
                message=error_messages[7000],
            )
            raise HTTPException(status_code=403, detail=error_response)

        data = ROLE_ACCESS[function_name]
        common_item = set(role) & set(data)
        if not common_item:
            error_response = error_response_model(code=401, error_code=4001)
            define_logger(
                level=30,
                request=request,
                user=user,
                loggName=loggername,
                pid=pid,
                message=error_messages[4001],
            )
            raise HTTPException(status_code=401, detail=error_response)
        return True

    define_logger(
        level=40,
        request=request,
        user=user,
        loggName=loggername,
        pid=pid,
        message=error_messages[7000],
    )
    error_response = error_response_model(code=422, error_code=7000)
    raise HTTPException(status_code=422, detail=error_response)


def auditloginfo(uid: str, name: str, ops: OperationType, prefix: str = None):
    """
    Function to generate the audit log info.
    """
    if ops == OperationType.CREATE.value:
        if prefix:
            return {
                f"{prefix}.created_on": local_time_to_gmt_epoch(),
                f"{prefix}.created_by": name,
                f"{prefix}.created_id": uid,
            }
        return {
            "created_on": local_time_to_gmt_epoch(),
            "created_by": name,
            "created_id": uid,
        }
    if ops == OperationType.UPDATE.value:
        if prefix:
            return {
                f"{prefix}.modified_on": local_time_to_gmt_epoch(),
                f"{prefix}.modified_by": name,
                f"{prefix}.modified_id": uid,
            }
        return {
            "modified_on": local_time_to_gmt_epoch(),
            "modified_by": name,
            "modified_id": uid,
        }


def create_unique_index(
    collection_name: str,
    field: str,
    user: dict = None,
    request=None,
):
    """Create a Unique index for the given field if it's not already created"""
    loggername = inspect.stack()[0]
    pid = os.getpid()
    try:
        collection: Collection = database[collection_name]
        index_info = collection.index_information()
        if field not in index_info:
            return collection.create_index([(field, 1)], unique=True)
        return None
    except PyMongoError as exc:

        define_logger(
            level=50,
            request=request,
            user=user,
            loggName=loggername,
            pid=pid,
            message=exc,
        )


def create_compond_index(
    collection_name: str,
    field: list,
    user: dict = None,
    request=None,
):
    """Create a Unique index for the given field if it's not already created"""
    loggername = inspect.stack()[0]
    pid = os.getpid()
    try:
        collection: Collection = database[collection_name]
        index_info = collection.index_information()
        if field not in index_info:
            collection.create_index(
                [("name", 1), ("type", 1), ("parent", 1), ("store_id", 1)],
                unique=True,
            )
        return None
    except PyMongoError as exc:
        error_response = error_response_model(code=500, error_code=3000)
        define_logger(
            level=50,
            request=request,
            user=user,
            loggName=loggername,
            pid=pid,
            message=error_messages[3000],
        )
        raise HTTPException(status_code=500, detail=error_response) from exc


# Function to encrypt a string
def encrypt_string(plain_text):
    fernet = Fernet(KEY)

    # Check if plain_text is already in bytes, if not, encode it
    if isinstance(plain_text, str):
        plain_text = plain_text.encode()  # Convert to bytes if it's a string

    encrypted_password = fernet.encrypt(plain_text)
    return encrypted_password.decode()  # Return as a string


# Function to decrypt a string
def decrypt_string(encrypted_text):
    fernet = Fernet(KEY)

    # Ensure the encrypted_text is in bytes, if it's a string, encode it
    if isinstance(encrypted_text, str):
        encrypted_text = encrypted_text.encode()  # Convert to bytes if it's a string

    decrypted_text = fernet.decrypt(
        encrypted_text
    ).decode()  # Decrypt and convert back to string
    return decrypted_text


def generate_passcode() -> str:
    return str(random.randint(1000, 9999))


def initialize_audit_log(current_user, existing_audit_log=None):
    """Initialize or update the audit log based on whether it's a new or modified entity."""
    timestamp = int(datetime.utcnow().timestamp())

    # Extract user details
    first_name = current_user["firstName"]
    last_name = current_user["lastName"] if current_user.get("lastName") != " " else ""
    user_name = f"{first_name} {last_name}"
    user_id = current_user["attributes"]["user_id"][0].upper()

    # If this is an existing entity, update the modification details
    if existing_audit_log:
        # If existing_audit_log is a dict, convert it to AuditLogInfoType
        if isinstance(existing_audit_log, dict):
            existing_audit_log = AuditLogInfoType(**existing_audit_log)

        # Modify the existing audit log without changing creation details
        existing_audit_log.modified_by = user_name
        existing_audit_log.modified_id = user_id
        existing_audit_log.modified_on = timestamp

        return existing_audit_log

    else:
        # Return a new instance of AuditLogInfoType with creation details
        return AuditLogInfoType(
            created_by=user_name,
            created_id=user_id,
            created_on=timestamp,
        )


def generate_epoch_with_string(append_str):
    # Get the current epoch time in seconds
    epoch_time = int(time.time())

    # Convert epoch time to string and append the provided string
    result = f"{epoch_time}_{append_str}"

    return result
