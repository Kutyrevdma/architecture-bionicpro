import os
import secrets
import uuid
import requests
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from keycloak import KeycloakOpenID

app = FastAPI()

# Configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "reports-frontend")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "secret")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
KEYCLOAK_EXTERNAL_URL = "http://localhost:8080"
REPORTS_SERVICE_URL = os.getenv("REPORTS_SERVICE_URL", "http://reports-service:8000")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keycloak Client
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_URL + "/",
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=False
)

sessions = {}
pkce_storage = {}

@app.get("/login")
def login():
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = keycloak_openid.calculate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(16)
    pkce_storage[state] = code_verifier

    auth_url = keycloak_openid.auth_url(
        redirect_uri=f"http://localhost:8000/callback",
        scope="openid profile email",
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256"
    )

    if "keycloak:8080" in auth_url:
        auth_url = auth_url.replace("keycloak:8080", "localhost:8080")

    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(code: str, state: str, response: Response):
    if state not in pkce_storage:
        raise HTTPException(status_code=400, detail="Invalid state")

    code_verifier = pkce_storage.pop(state)

    try:
        token_response = keycloak_openid.token(
            grant_type="authorization_code",
            code=code,
            redirect_uri=f"http://localhost:8000/callback",
            code_verifier=code_verifier
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = token_response

    response = RedirectResponse(url=FRONTEND_URL)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=300
    )
    return response

@app.get("/api/userinfo")
def user_info(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = sessions[session_id]
    access_token = session_data["access_token"]
    refresh_token = session_data["refresh_token"]

    try:
        userinfo = keycloak_openid.userinfo(access_token)
    except Exception:
        try:
            new_tokens = keycloak_openid.refresh_token(refresh_token)
            session_data.update(new_tokens)
            access_token = session_data["access_token"]
            userinfo = keycloak_openid.userinfo(access_token)
        except Exception:
            del sessions[session_id]
            raise HTTPException(status_code=401, detail="Session expired")

    new_session_id = secrets.token_urlsafe(32)
    sessions[new_session_id] = session_data
    del sessions[session_id]

    response.set_cookie(
        key="session_id",
        value=new_session_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=300
    )

    return {"user": userinfo, "new_session_id": new_session_id}

@app.get("/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]

    response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("session_id")
    return response

@app.get("/reports")
def get_reports(request: Request):
    """
    Proxy request to Reports Service.
    Enforces security: Uses the authenticated user's ID from session.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = sessions[session_id]

    # Get User Info to find the ID (sub or preferred_username)
    # We might have cached it, or we fetch it. user_info endpoint fetches it.
    access_token = session_data["access_token"]
    try:
        userinfo = keycloak_openid.userinfo(access_token)
        user_id = userinfo.get("preferred_username") # Or "sub" depending on what we use in DB
        # For our mock seed, we used usernames like "user1", so use preferred_username.

        if not user_id:
             raise HTTPException(status_code=400, detail="User ID not found in token")

        # Call Reports Service
        # We pass user_id in URL. We could also pass a service token if we had inter-service auth.
        resp = requests.get(f"{REPORTS_SERVICE_URL}/reports/{user_id}")

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"message": "Report not found"}
        else:
            raise HTTPException(status_code=resp.status_code, detail="Error fetching report")

    except Exception as e:
        print(f"Error in proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
