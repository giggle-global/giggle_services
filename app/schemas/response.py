# app/schemas/response.py
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    status_code: int
    message: str
    data: Optional[T] = None

def ok(data: Optional[T] = None, message: str = "OK", status_code: int = 200) -> APIResponse[T]:
    return APIResponse[T](status_code=status_code, message=message, data=data)
