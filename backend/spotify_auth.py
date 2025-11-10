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

# backend/spotify_auth.py
"""
Spotify OAuth + simple Spotify passthrough endpoints used by the web UI.
- GET  /auth/login         -> redirect to Spotify (forces scope re-consent)
- GET  /auth/callback      -> exchange code, redirect to FRONTEND_URL with tokens in hash
- GET  /spotify/me         -> profile via Spotify API (requires access_token)
- GET  /spotify/playlists  -> playlists via Spotify API (requires access_token)
- GET  /spotify/top-artists-> top artists via Spotify API (requires access_token)
- GET  /spotify/check-top  -> debug helper
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

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500/")

# Scopes needed for profile, playlists, top artists, and recently played:
SCOPES = "user-read-email playlist-read-private user-top-read user-read-recently-played"

TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"


def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(raw).decode()


@router.get("/auth/login", summary="Redirect to Spotify login", tags=["Auth"])
def spotify_login(state: Optional[str] = None):
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_REDIRECT_URI:
        raise HTTPException(500, "Spotify env vars not configured")
    # Pass the frontend URL via state; force re-consent so scopes are guaranteed
    st = urllib.parse.quote_plus(FRONTEND_URL if not state else state)
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
        "state": st,
        "show_dialog": "true",  # force re-consent so we always get needed scopes
    }
    return RedirectResponse(AUTHORIZE_URL + "?" + urllib.parse.urlencode(params))


@router.get("/auth/callback", summary="Spotify callback → exchange code → redirect to web UI with tokens", tags=["Auth"])
def spotify_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    if error or not code:
        raise HTTPException(400, f"Spotify auth error: {error or 'missing code'}")

    token_res = requests.post(
        TOKEN_URL,
        headers={"Authorization": _basic_auth_header()},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": SPOTIFY_REDIRECT_URI},
        timeout=15,
    )
    if token_res.status_code != 200:
        raise HTTPException(400, f"Token exchange failed: {token_res.text}")

    tokens = token_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")

    me = spotify_get("/me", access_token)
    if isinstance(me, dict) and "error" in me:
        raise HTTPException(400, f"/me failed: {me}")

    app_token = create_access_token(subject=me.get("id", "unknown"))
    target = urllib.parse.unquote_plus(state) if state else FRONTEND_URL
    fragment = urllib.parse.urlencode({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "app_token": app_token,
        "display_name": me.get("display_name") or "",
        "spotify_id": me.get("id") or ""
    })
    return RedirectResponse(f"{target}#{fragment}")


# --------- Passthrough endpoints used by the UI ---------

@router.get("/spotify/me", summary="Return Spotify profile (requires access_token)", tags=["Spotify"])
def get_me(access_token: str = Query(..., description="Spotify access token")):
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
    data = spotify_get("/me/playlists", access_token, params={"limit": limit, "offset": offset})
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(400, f"/me/playlists failed: {data}")
    return data


@router.get("/spotify/top-artists", summary="Return user's top artists (requires access_token)", tags=["Spotify"])
def get_top_artists(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = 10,
    offset: int = 0
):
    data = spotify_get("/me/top/artists", access_token, params={"limit": limit, "offset": offset})
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(400, f"/me/top/artists failed: {data}")
    return data


# Debug helper to validate top artists quickly
@router.get("/spotify/check-top")
def check_top(access_token: str, limit: int = 10):
    data = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    items = data.get("items", []) if isinstance(data, dict) else []
    names = [a.get("name") for a in items if a]
    return {"count": len(names), "names": names}
