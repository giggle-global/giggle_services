"""Logging Module"""
from datetime import datetime
import os
import logging
import inspect
import pytz
from logging.handlers import RotatingFileHandler
from pymongo.collection import Collection
from fastapi import  Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from app.core.db import database

from app.core.models.audit_log import AuditLogInfoType, BaseAuditLog


def define_logger(level:int, user:dict=None, request:Request=None, loggName:inspect.FrameInfo=None, pid:int=None, message:str=None, body:dict=None):
    """
    function to write loggs in logg file.

    MANDATORY :

    level :
    10: DEBUG , 20: INFO , 30: WARNING , 40: ERROR , 50: CRITICAL

    OPTIONAL :

    user: user information, 
    request: request class, 
    loggname: inspect file name and function name, 
    pid: current proccess ID, 
    message: message, 
    body: request body data
    """
    txt = ''
    try:
        if user != None:
            txt += f'- USER: {user["user_id"]} '
    except:
        pass
    try:
        if request != None:
            txt += f'- IP: {request.client.host} - URL: {request.method} {request.url} '
    except:
        pass
    try:
        if message != None:
            txt += f'- MESSAGE: {message} '
    except:
        pass
    try:
        if pid != None:
            txt += f'- PID: {pid} '
    except:
        pass
    try:
        if loggName != None:
            txt += f'- FILE: {loggName[1]}:{loggName[3]} '
    except:
        pass
    try:
        if body != None:
            txt += f'- BODY: {body} '
    except:
        pass

    try:
        log.log(level=level, msg=txt)
    except :
        log.log(level=10, msg="Logger Debug Error")

def get_logger():
    """
    create and return a logger object 
    """
    # Create a logger
    logger = logging.getLogger('ASMP')

    log_directory = os.path.abspath("logger")
    os.makedirs(log_directory, exist_ok=True)
    log_file_path = os.path.join(log_directory, "backend.log")

    # Set the logging level (you can adjust this based on your needs)
    logger.setLevel(logging.DEBUG)
    

    # Create a file handler and set the level to DEBUG
    file_handler = RotatingFileHandler(
        log_file_path,
        backupCount=21,
        maxBytes= 1024 * 1024 * 20  # 20 MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.suffix = "%Y-%m-%d"

    # Create a console handler and set the level to INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    # Create a formatter and attach it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

log = get_logger()

def add_audit_log(user: dict, ref_id: str, data: dict, collection : Collection, event_type: str, record_type: str):
    """
    Adding an audit log entry
    """
    # Getting the current epoch time
    current_local_time = datetime.now()
    gmt_timezone = pytz.timezone('UTC')
    current_gmt_time = current_local_time.astimezone(gmt_timezone)
    epoch = datetime(1970, 1, 1, tzinfo=pytz.utc)
    diff = current_gmt_time - epoch
    timestamp = int(diff.total_seconds())
    audit_log_user_info = AuditLogInfoType()
    if user:
        if event_type == "CREATE":
            audit_log_user_info = AuditLogInfoType(created_by=f"{user['firstName']} {user['lastName']}", created_id=user["attributes"]["user_id"][0].upper(), created_on=timestamp)
        elif event_type == "UPDATE":
            audit_log_user_info = AuditLogInfoType(modified_by=f"{user['firstName']} {user['lastName']}", modified_id=user["attributes"]["user_id"][0].upper(), modified_on=timestamp)
        elif event_type == "DELETE":
            audit_log_user_info = AuditLogInfoType(modified_by=f"{user['firstName']} {user['lastName']}", modified_id=user["attributes"]["user_id"][0].upper(), modified_on=timestamp)

    audit_log_data = BaseAuditLog(event_type=event_type, ref_id=ref_id, data=data, record_type=record_type, auditlog_info=audit_log_user_info)

    # Convert ObjectId to string in the audit_log_data
    def convert_objectid_to_str(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_objectid_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_objectid_to_str(i) for i in obj]
        return obj

    audit_log_data_dict = convert_objectid_to_str(audit_log_data.model_dump())
    audit_log_data_dict = jsonable_encoder(audit_log_data_dict)
    collection.insert_one(audit_log_data_dict)