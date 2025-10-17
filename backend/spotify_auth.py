# backend/spotify_auth.py
"""
@Author: Tuniverse Team
@Version: 1.0
@Since: 2025-10-17

Usage:
    - Add this file as backend/spotify_auth.py
    - Ensure env vars are set:
        SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
      Example (Windows CMD):
        set SPOTIFY_CLIENT_ID=...
        set SPOTIFY_CLIENT_SECRET=...
        set SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/auth/callback
    - In backend/main.py:
        from . import spotify_auth
        app.include_router(spotify_auth.router)

Notes:
    - This uses Authorization Code flow with client secret (local dev).
    - For production / public mobile client, use PKCE flow.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from typing import Optional
import os, urllib.parse, base64, requests

from .auth import create_access_token  # your local JWT helper
from .spotify_client import spotify_get, refresh_spotify_token

router = APIRouter()

# ---------- Config ----------
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
SCOPES = "user-read-email playlist-read-private user-top-read user-read-recently-played"

TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"

def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(raw).decode()

# ---------- OAuth Endpoints ----------

@router.get("/auth/login", summary="Redirect to Spotify login")
def spotify_login(state: Optional[str] = None):
    """
    Step 1: Send user to Spotify to consent with our scopes.
    """
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_REDIRECT_URI:
        raise HTTPException(500, "Spotify env vars not configured")

    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
    }
    if state:
        params["state"] = state  # optional CSRF token if you add it later

    return RedirectResponse(AUTHORIZE_URL + "?" + urllib.parse.urlencode(params))


@router.get("/auth/callback", summary="Handle Spotify redirect; exchange code for tokens")
def spotify_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """
    Step 2: Spotify redirects here with ?code=...
    We exchange code -> access_token (+ refresh_token), then fetch /me and a playlists preview.
    """
    if error or not code:
        raise HTTPException(400, f"Spotify auth error: {error or 'missing code'}")

    # Exchange authorization code for tokens
    token_res = requests.post(
        TOKEN_URL,
        headers={"Authorization": _basic_auth_header()},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
        timeout=15,
    )
    if token_res.status_code != 200:
        raise HTTPException(400, f"Token exchange failed: {token_res.text}")

    tokens = token_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    # Fetch Spotify profile (proves the token works)
    me = spotify_get("/me", access_token)
    if "error" in me:
        raise HTTPException(400, f"/me failed: {me}")

    # Optional: small playlists preview for demo
    playlists = spotify_get("/me/playlists", access_token, params={"limit": 5})
    if "error" in playlists:
        playlists_preview = {"error": playlists}
    else:
        playlists_preview = [
            {"name": p.get("name"), "id": p.get("id")}
            for p in playlists.get("items", [])
        ]

    # Issue your own app JWT (subject = spotify user id)
    app_token = create_access_token(subject=me.get("id", "unknown"))

    return {
        "message": "Spotify auth OK",
        "spotify_user": {"id": me.get("id"), "email": me.get("email"), "display_name": me.get("display_name")},
        "access_token": access_token,          # return for dev convenience
        "refresh_token": refresh_token,        # return for dev convenience
        "app_token": app_token,                # your JWT for your own APIs
        "playlists_preview": playlists_preview
    }

# ---------- Simple test endpoints (optional but useful for /docs demo) ----------

@router.get("/spotify/me", summary="Return Spotify profile (requires access_token)")
def get_me(access_token: str):
    """
    Quick tester: paste access_token from callback into the 'access_token' query param.
    """
    data = spotify_get("/me", access_token)
    if "error" in data:
        raise HTTPException(400, f"/me failed: {data}")
    return data


@router.get("/spotify/playlists", summary="Return Spotify playlists (requires access_token)")
def get_playlists(access_token: str, limit: int = 10, offset: int = 0):
    """
    Quick tester: lists playlists with pagination params.
    """
    data = spotify_get("/me/playlists", access_token, params={"limit": limit, "offset": offset})
    if "error" in data:
        raise HTTPException(400, f"/me/playlists failed: {data}")
    return data


@router.get("/auth/refresh", summary="Refresh Spotify access token (requires refresh_token)")
def refresh_token(refresh_token: str):
    """
    Exchanges a refresh_token for a new access_token.
    """
    refreshed = refresh_spotify_token(refresh_token)
    if not refreshed:
        raise HTTPException(400, "Refresh failed")
    return refreshed
