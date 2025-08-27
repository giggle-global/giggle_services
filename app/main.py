from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
from starlette.responses import JSONResponse
from app.schemas.response import APIResponse

from app.core.db import check_db_connection
from app.services.user import UserService


from app.routes import user
from app.routes import auth
from app.routes import chat
from app.routes import request
from app.routes import ticket
import time

import logging

logging.basicConfig(
    level=logging.DEBUG,   # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                    # console
        logging.FileHandler("app.log", "a"),   # file
    ]
)

# Turn down noisy loggers
for noisy in (
    "pymongo",              # all pymongo logs
    "pymongo.topology",     # heartbeats
    "pymongo.connection",
    "pymongo.pool",
):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("App started")




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global exception handlers -> uniform response ---
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    body = APIResponse(status_code=exc.status_code, message=str(exc.detail), data=None)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    body = APIResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                       message="Validation error",
                       data={"errors": exc.errors()})
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=body.model_dump())

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    # Tip: log exc with traceback here
    body = APIResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                       message="Something went wrong",
                       data=None)
    return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump())



app.include_router(user.router)
app.include_router(auth.router)
app.include_router(request.router)
app.include_router(chat.router)
app.include_router(ticket.router)


user_service = UserService()


@app.on_event("startup")
def on_startup():
    time.sleep(1)  # Wait for DB to be ready
    """This function will be executed when the server starts"""
    user_service.create_root_user()

@app.get("/health")
def health_check():
    return {"status": "ok"}
