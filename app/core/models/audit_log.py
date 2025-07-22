""" To support creation and update APIs"""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel 
from pydantic import field_validator
from pydantic import FieldValidationInfo



class OperationType(str,Enum):
    """Enum to define Operation Type"""
    CREATE = 'CREATE'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'


class AuditLogInfoType(BaseModel):
    """Base AuditLoInfoType for creation"""
    created_by: Optional[str] = None
    created_id: Optional[str] = None
    created_on: Optional[int] = None
    modified_by: Optional[str] = None
    modified_id: Optional[str] = None
    modified_on: Optional[int] = None




class BaseAuditLog(BaseModel):
    """Base AuditLog details schema for creation"""
    time_stamp: Optional[int] = int(datetime.utcnow().timestamp())
    event_type: OperationType
    record_type: str
    ref_id: Optional[str]
    data: Optional[dict]
    auditlog_info: Optional[AuditLogInfoType]

    @field_validator("ref_id")
    @classmethod
    def validate_document_id(cls, value, info: FieldValidationInfo):
        "Validating document id"
        if info.data["event_type"] in (OperationType.CREATE, OperationType.UPDATE, OperationType.DELETE) and value is None:
            raise ValueError(
                "refId is required for create or update or delete operations")
        return value

    @field_validator("data")
    @classmethod
    def validate_full_document(cls, value, info: FieldValidationInfo):
        "validating Full data"
        if info.data["event_type"] in (OperationType.CREATE.value, OperationType.UPDATE.value, OperationType.DELETE.value) and value is None:
            raise ValueError(
                "full_document is required for create or update or delete operations")
        return value
