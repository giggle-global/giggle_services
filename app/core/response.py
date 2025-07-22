from fastapi.responses import JSONResponse
from app.core.constant import error_messages, http_messages


def response_model_items(data, message, code, count: int = None, version: float = None):
    """General Response format"""
    if hasattr(data, "dict"):
        data = data.dict()

    content = {"status": code, "message": message}

    if version is not None:
        content["version"] = version
        
    if count is not None:
        content["total"] = count

    content["data"] = data

    return JSONResponse(content=content, status_code=code)


def error_response_model(code, error_code):
    """Error Response format"""
    return {
        "status": code,
        "message": http_messages[code],
        "error": {
            "error_code": error_code,
            "details": error_messages[error_code]
        }
    }
