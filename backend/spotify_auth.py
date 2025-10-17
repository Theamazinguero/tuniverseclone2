# backend/spotify_auth.py
"""
@Author: Tuniverse Team
@Version: 1.0
@Since: 2025-10-17

Usage:
    1) Set environment variables (Windows CMD example):
        set SPOTIFY_CLIENT_ID=...
        set SPOTIFY_CLIENT_SECRET=...
        set SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/auth/callback
        set SECRET_KEY=dev-secret-key

    2) In backend/main.py:
        from . import spotify_auth
        app.include_router(spotify_auth.router)

    3) Run:
        venv\Scripts\activate
        python -m uvicorn backend.main:app --reload
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from typing import Optional
import os
import urllib.parse
import base64
import requests

from .auth import create_access_token
from .spotify_client import spotify_get, refresh_spotify_token

router = APIRouter()

# ---------- Config ----------
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")

# Requested scopes (adjust as needed)
SCOPES = "user-read-email playlist-read-private user-top-read user-read-recently-played"

TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"


def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(raw).decode()


# ---------- OAuth Flow ----------

@router.get("/auth/login", summary="Redirect to Spotify login", tags=["Auth"])
def spotify_login(state: Optional[str] = None):
    """
    Step 1: Send user to Spotify to consent with our scopes.
    Do NOT call via /docs (AJAX can't follow cross-origin redirects). Open in browser.
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
        params["state"] = state  # optional CSRF token

    auth_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(auth_url)


@router.get("/auth/callback", summary="Handle Spotify redirect; exchange code for tokens", tags=["Auth"])
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
    if isinstance(me, dict) and "error" in me:
        raise HTTPException(400, f"/me failed: {me}")

    # Optional: small playlists preview for demo
    playlists = spotify_get("/me/playlists", access_token, params={"limit": 5})
    if isinstance(playlists, dict) and "error" in playlists:
        playlists_preview = {"error": playlists}
    else:
        playlists_preview = [
            {"name": p.get("name"), "id": p.get("id")}
            for p in (playlists or {}).get("items", [])
        ]

    # Issue your own app JWT (subject = spotify user id)
    app_token = create_access_token(subject=me.get("id", "unknown"))

    return {
        "message": "Spotify auth OK",
        "spotify_user": {
            "id": me.get("id"),
            "email": me.get("email"),
            "display_name": me.get("display_name"),
        },
        "access_token": access_token,     # return for dev/demo convenience
        "refresh_token": refresh_token,   # return for dev/demo convenience
        "app_token": app_token,           # your JWT for your own APIs
        "playlists_preview": playlists_preview,
    }


@router.get("/auth/refresh", summary="Refresh Spotify access token (requires refresh_token)", tags=["Auth"])
def refresh_token(refresh_token: str):
    """
    Exchanges a refresh_token for a new access_token.
    """
    refreshed = refresh_spotify_token(refresh_token)
    if not refreshed:
        raise HTTPException(400, "Refresh failed")
    return refreshed


# ---------- Simple Data Endpoints (use access_token from callback) ----------

@router.get("/spotify/me", summary="Return Spotify profile (requires access_token)", tags=["Spotify"])
def get_me(access_token: str = Query(..., description="Spotify access token")):
    """
    Quick tester: paste access_token from /auth/callback into this query param.
    """
    data = spotify_get("/me", access_token)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(400, f"/me failed: {data}")
    return data


@router.get("/spotify/playlists", summary="Return Spotify playlists (requires access_token)", tags=["Spotify"])
def get_playlists(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = 10,
    offset: int = 0,
):
    """
    Lists playlists with pagination params.
    """
    data = spotify_get("/me/playlists", access_token, params={"limit": limit, "offset": offset})
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(400, f"/me/playlists failed: {data}")
    return data


@router.get("/spotify/top-artists", summary="Return user's top artists (requires access_token)", tags=["Spotify"])
def get_top_artists(access_token: str = Query(..., description="Spotify access token"), limit: int = 10, offset: int = 0):
    """
    Fetch user's top artists from Spotify.
    """
    data = spotify_get("/me/top/artists", access_token, params={"limit": limit, "offset": offset})
    if not isinstance(data, dict) or "items" not in data:
        return {"error": "Could not fetch top artists", "details": data}

    artists = []
    for artist in data["items"]:
        artists.append({
            "name": artist.get("name"),
            "genres": artist.get("genres", []),
            "popularity": artist.get("popularity", 0),
            "id": artist.get("id"),
        })

    return {"count": len(artists), "top_artists": artists}
