from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import user
from app.services.user import UserService
from app.routes import auth


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


user_service = UserService()


@app.on_event("startup")
def on_startup():
    """This function will be executed when the server starts"""
    user_service.create_root_user()
