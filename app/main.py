from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
from starlette.responses import JSONResponse, Response
from app.schemas.response import APIResponse

from app.core.db import check_db_connection
from app.services.user import UserService
from app.services.skill import SkillService



from app.routes import user
from app.routes import auth
from app.routes import chat
from app.routes import request
from app.routes import ticket
from app.routes import project
from app.routes import token
from app.routes import review
from app.routes import agreements
from app.routes import milestones
from app.routes import portfolio
from app.routes import matching
from app.routes import otp
from app.routes import notification
from app.routes import meeting
from app.core.scheduler import milestone_scheduler
import time

import logging

logging.basicConfig(
    level=logging.INFO,   # INFO, WARNING, ERROR, CRITICAL (changed from DEBUG for performance)
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

# Enhanced CORS configuration
# Note: When allow_credentials=True, we MUST specify origins explicitly (cannot use "*")
# For production, set ALLOWED_ORIGINS environment variable
import os
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
if ALLOWED_ORIGINS_ENV:
    # Parse comma-separated origins from environment variable
    allowed_origins = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
else:
    # Default origins for development and production
    # In production, set ALLOWED_ORIGINS="https://begiggle.keydraft.com,https://www.begiggle.keydraft.com"
    env = os.getenv("ENVIRONMENT", "development")
    if env == "development":
        # Allow common development origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    else:
        # Production: must specify exact origins
        allowed_origins = [
            "https://begiggle.keydraft.com",
            "https://www.begiggle.keydraft.com",
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
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
    # Log the exception with full traceback for debugging
    logger.exception("Unhandled exception occurred: %s", str(exc))
    body = APIResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                       message="Something went wrong",
                       data=None)
    return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump())



app.include_router(user.router)
app.include_router(auth.router)
app.include_router(request.router)
app.include_router(chat.router)
app.include_router(ticket.router)
app.include_router(project.router)
app.include_router(token.router)
app.include_router(review.router)
app.include_router(agreements.router)
app.include_router(milestones.router)
app.include_router(portfolio.router)
app.include_router(matching.router)
app.include_router(otp.router)
app.include_router(notification.router)
app.include_router(meeting.router)


user_service = UserService()


@app.on_event("startup")
def on_startup():
    time.sleep(1)  # Wait for DB to be ready
    """This function will be executed when the server starts"""
    user_service.create_root_user()
    skill_service = SkillService()
    skill_service.seed_skills_if_missing()
    
    # Validate email configuration on startup
    from app.core.config import config
    from app.core.email_service import EmailService
    email_provider = config.get("email_provider", "smtp").lower()
    logger.info("Email provider configured: %s", email_provider)
    
    if email_provider == "smtp":
        smtp_server = config.get("smtp_server")
        smtp_username = config.get("smtp_username")
        if not smtp_server or not smtp_username:
            logger.warning("SMTP configuration incomplete. SMTP_SERVER=%s, SMTP_USERNAME=%s", 
                         smtp_server, smtp_username)
        else:
            logger.info("SMTP configuration validated: server=%s, username=%s", 
                       smtp_server, smtp_username)
    elif email_provider == "ses":
        ses_from = config.get("ses_from_email")
        aws_key = config.get("aws_access_key")
        if not ses_from or not aws_key:
            logger.warning("SES configuration incomplete. SES_FROM_EMAIL=%s, AWS_ACCESS_KEY=%s", 
                         ses_from, "***" if aws_key else None)
        else:
            logger.info("SES configuration validated")
    
    # Start milestone reminder scheduler
    try:
        milestone_scheduler.start()
        logger.info("Milestone reminder scheduler started")
    except Exception as e:
        logger.error("Failed to start milestone scheduler: %s", e)

@app.on_event("shutdown")
def on_shutdown():
    """Cleanup on server shutdown"""
    try:
        milestone_scheduler.stop()
        from app.core.rabbitmq import RabbitMQConnection
        RabbitMQConnection.close()
        logger.info("Scheduler and RabbitMQ connections closed")
    except Exception as e:
        logger.error("Error during shutdown: %s", e)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/health/config")
def health_check_config():
    """Diagnostic endpoint to check email configuration (without sensitive data)"""
    from app.core.config import config
    return {
        "status": "ok",
        "email_provider": config.get("email_provider", "not set"),
        "smtp_server": config.get("smtp_server", "not set") or "not set",
        "smtp_port": config.get("smtp_port", "not set"),
        "smtp_username": config.get("smtp_username", "not set") or "not set",
        "smtp_from_email": config.get("smtp_from_email", "not set") or "not set",
        "smtp_configured": bool(
            config.get("smtp_server") and 
            config.get("smtp_username") and 
            config.get("smtp_password")
        ),
        "ses_configured": bool(
            config.get("ses_from_email") and 
            config.get("aws_access_key") and 
            config.get("aws_secret_key")
        )
    }
