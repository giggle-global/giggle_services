import requests, os, json, inspect
from dataclasses import asdict
from app.core.config import config
from keycloak import KeycloakOpenID, KeycloakAdmin
from base64 import b64decode
from jwt.exceptions import DecodeError, InvalidTokenError
from app.core.audit_log import define_logger

from cryptography.hazmat.primitives import serialization
import jwt

from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader

# Keycloak Configuration
KEYCLOAK_URL = config["keyclock_url"]
REALM_NAME = config["realm_name"]
CLIENT_ID = config["client_id"]
CLIENT_SECRET = config["client_secret"]

# Initialize Keycloak OpenID Client
keycloak_openid = KeycloakOpenID(
    server_url=f"{KEYCLOAK_URL}/",
    client_id=CLIENT_ID,
    realm_name=REALM_NAME,
    client_secret_key=CLIENT_SECRET,
)

# OAuth2 scheme for token retrieval
oauth2_scheme = APIKeyHeader(name="Authorization")


def keycloak_instance():
    """Initialize KeycloakAdmin instance"""
    keycloak_admin = KeycloakAdmin(
        server_url=f"{KEYCLOAK_URL}/",
        client_id=CLIENT_ID,
        realm_name=REALM_NAME,
        client_secret_key=CLIENT_SECRET,
        verify=True,
    )
    return keycloak_admin


def get_client_access_token():
    """Get an access token using client credentials."""
    url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    token = response.json()
    access_token = token["access_token"]
    #     print(f"Client Access Token: {access_token}")
    if access_token is None:
        define_logger(
            level=40,
            message="Client Access Token for keycloak not found",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
        raise HTTPException(
            status_code=500, detail="Client Access Token for keycloak not found"
        )
    return access_token


def create_user_in_keycloak(user_data):
    token = get_client_access_token()
    """Create a user in Keycloak using the client access token and return the Keycloak user ID."""
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(url, json=user_data, headers=headers)

    if response.status_code == 201:
        # Extract the Keycloak user ID from the 'Location' header
        location_header = response.headers.get("Location")
        if location_header:
            # The location URL will be something like:
            # http://keycloak-server/auth/admin/realms/{realm}/users/{user_id}
            keycloak_user_id = location_header.split("/")[-1]
            define_logger(
                level=20,
                message=f"User {user_data['username']} created with Keycloak ID {keycloak_user_id}",
                pid=os.getpid(),
                loggName=inspect.stack()[0],
            )
            return keycloak_user_id
        else:
            define_logger(
                level=40,
                message=f"User {user_data['username']} created but Keycloak ID not found",
                pid=os.getpid(),
                loggName=inspect.stack()[0],
            )
            raise HTTPException(
                status_code=500,
                detail=f"User {user_data['username']} created but Keycloak ID not found",
            )
    else:
        define_logger(
            level=40,
            message=f"Failed to create user {user_data['username']}: {response.content}",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user {user_data['username']}: {response.content}",
        )


def update_user_in_keycloak(token, keycloak_id, updated_data):

    # Proceed with the update if the checks pass
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users/{keycloak_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Send the PUT request
    response = requests.put(url, json=updated_data, headers=headers)

    if response.status_code == 204:
        define_logger(
            level=20,
            message=f"User with ID {keycloak_id} updated successfully",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )

    else:
        define_logger(
            level=40,
            message=f"Failed to update user with ID {keycloak_id}: {response.content}",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user with ID {keycloak_id}: {response.content}",
        )


def get_current_user(token: str = Depends(oauth2_scheme)):

    try:
        if token.startswith("Bearer "):
            token = token[len("Bearer ") :]

        key_der_base64 = keycloak_openid.public_key()
        key_der = b64decode(key_der_base64.encode())
        public_key = serialization.load_der_public_key(key_der)

        # Decode JWT token
        user_base_detail = jwt.decode(
            token, public_key, algorithms=["RS256"], audience="account"
        )

        # Debugging: print decoded user details
        # print("Decoded user details:", user_base_detail)
        keycloak_admin = keycloak_instance()
        sid = user_base_detail["sid"]
        # Check if the token is active and user exists
        if "sub" in user_base_detail:
            user = keycloak_admin.get_user(user_base_detail["sub"])
            if user:
                enabled = user.get("enabled")
                if not enabled:
                    raise HTTPException(status_code=401, detail="User is disabled")
                user["sid"] = sid
                print("User details:", user)
                return user
            else:
                define_logger(
                    level=40,
                    message="User not found",
                    pid=os.getpid(),
                    loggName=inspect.stack()[0],
                )
                raise HTTPException(status_code=404, detail="User not found")

        # If 'sub' is missing, token might be malformed
        define_logger(
            level=40,
            message="Invalid token structure",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )

        # If 'sub' is missing, token might be malformed
        raise HTTPException(status_code=400, detail="Invalid token structure")

    except (DecodeError, InvalidTokenError) as exception:
        define_logger(
            level=40,
            message="Invalid or expired token",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
        # Handle JWT decoding errors
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        ) from exception

    except HTTPException as exception:
        # Pass through known HTTP errors
        define_logger(
            level=40,
            message="Unknown HTTP error",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
            body={"error": str(exception)},
        )
        raise HTTPException(
            status_code=exception.status_code, detail=exception.detail
        ) from exception

    except Exception as exception:
        # Catch all other errors
        define_logger(
            level=40,
            message="Internal Server Error",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
            body={"error": str(exception)},
        )
        raise HTTPException(
            status_code=500, detail="Internal Server Error"
        ) from exception


def authenticate_with_keycloak(username: str, passcode: str) -> dict:
    """Authenticate a user with Keycloak using their credentials."""
    token = get_client_access_token()
    url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": username,
        "password": passcode,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(url, data=data, headers=headers)

    if response.status_code == 200:
            # Return only needed fields
            resp = response.json()
            return {
                "access_token": resp["access_token"],
                "refresh_token": resp["refresh_token"],
                "expires_in": resp["expires_in"],
                "refresh_expires_in": resp["refresh_expires_in"],
                "token_type": resp["token_type"]
            }
    raise HTTPException(status_code=401, detail="Invalid username or password")


def set_user_password(token, keycloak_user_id, new_password, temporary=None):
    """
    Set a new password for a user in Keycloak, marking it as non-temporary.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users/{keycloak_user_id}/reset-password"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if temporary == True:
        temp = True
    else:
        temp = False
    # New password details
    data = {
        "type": "password",
        "temporary": temp,  # Set to False so that the password is no longer temporary
        "value": new_password,
    }

    # Send the password reset request
    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 204:
        None
    else:
        define_logger(
            level=40,
            message=f"Failed to update password for user {keycloak_user_id}",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
            body={"error": response.content},
        )

        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to update password for user {keycloak_user_id}: {response.content}",
        )


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh the access token using the refresh token.
    """
    url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"

    # Data for requesting a new access token
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Send the POST request to get the new access token
    response = requests.post(url, data=data, headers=headers)

    if response.status_code == 200:
        token_data = response.json()
        return {
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_in": token_data["expires_in"],
                "refresh_expires_in": token_data["refresh_expires_in"],
                "token_type": token_data["token_type"]
            }
    else:
        error_response = response.json()
        define_logger(
            level=40,
            message="Failed to refresh token",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
            body={"error": error_response.get("error_description", response.content)},
        )
        raise HTTPException(
            status_code=response.status_code,
            detail="Session expired. Please log in again.",
        )

def delete_user_in_keycloak(token, keycloak_user_id):
    """Delete a user in Keycloak using the client access token and return the Keycloak user ID.
    """
    keycloak_admin = keycloak_instance()
    keycloak_admin.delete_user(keycloak_user_id)
def logout_user_session(token, session_id):
    """
    Logout a specific user session in Keycloak.

    :param token: Admin access token
    :param session_id: ID of the session to logout
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/sessions/{session_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        define_logger(
            level=20,
            message=f"Session {session_id} logged out successfully",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
    elif response.content == b'{"error":"Sesssion not found"}':
        define_logger(
            level=40,
            message=f"Session {session_id} not found",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
    else:
        define_logger(
            level=40,
            message=f"Failed to logout session {session_id}",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
            body={"error": response.content},
        )
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to logout session {session_id}: {response.content}",
        )


def logout_all_user_sessions(token, keycloak_user_id):
    """
    Logout all active sessions for a user in Keycloak.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users/{keycloak_user_id}/logout"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(url, headers=headers)

    if response.status_code == 204:
        define_logger(
            level=20,
            message=f"All sessions for user {keycloak_user_id} logged out successfully",
            pid=os.getpid(),
            loggName=inspect.stack()[0],
        )
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to logout all sessions for user {keycloak_user_id}: {response.content}",
        )
