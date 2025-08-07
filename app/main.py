from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.user import UserService

from app.routes import user
from app.routes import auth
from app.routes import chat
from app.routes import request
from app.routes import ticket
import time


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(auth.router)
app.include_router(request.router)
app.include_router(chat.router)
app.include_router(ticket.router)


user_service = UserService()


@app.on_event("startup")
def on_startup():
    time.sleep(5)  # Wait for DB to be ready
    """This function will be executed when the server starts"""
    user_service.create_root_user()

@app.get("/health")
def health_check():
    return {"status": "ok"}
