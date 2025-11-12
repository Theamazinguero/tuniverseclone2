"""
Backend Passport Coding
@Author: Tyler Tristan
@Version: 1.0
@Since: 10/03/2025
Usage:
Generate the user's customized music passport
Change Log:
Version 1.0 (10/03/2025):
Created backend code for the music passport
"""

# backend/routers/passport.py
# Music Passport endpoints:
#  - GET /passport/{user_id}          -> DB-based summary (your original flow)
#  - GET /passport/from_token         -> Live snapshot from Spotify Top Artists (fast)
#  - GET /passport/from_token_recent  -> Live snapshot from Recently Played (fast)

# backend/routers/passport.py
# Music Passport endpoints:
#  - GET /passport/{user_id}     -> DB-based summary
#  - GET /passport/from_token    -> Live snapshot from Spotify Top Artists
#  - GET /passport/from_recent   -> Live snapshot from Recently Played

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
import os
import time
import requests

from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

# IMPORTANT:
# Do NOT put a prefix here; main.py will mount with prefix="/passport"
router = APIRouter(tags=["Music Passport"])

# ---------------- Config ----------------
USE_MB = os.getenv("PASSPORT_USE_MB", "0") == "1"  # set PASSPORT_USE_MB=1 to enable MB lookups

COUNTRY_TO_REGION = {
    "United States": "North America", "USA": "North America", "US": "North America",
    "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "UK": "Europe", "Ireland": "Europe",
    "Germany": "Europe", "France": "Europe", "Spain": "Europe", "Italy": "Europe",
    "Netherlands": "Europe", "Sweden": "Europe", "Norway": "Europe", "Finland": "Europe",
    "Denmark": "Europe", "Poland": "Europe", "Portugal": "Europe", "Russia": "Europe",
    "Japan": "Asia", "South Korea": "Asia", "Korea, Republic of": "Asia", "China": "Asia", "India": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America", "Colombia": "South America",
    "South Africa": "Africa", "Nigeria": "Africa", "Egypt": "Africa",
}

QUICK_COUNTRY_SEEDS: Dict[str, str] = {
    "Taylor Swift": "United States",
    "Drake": "Canada",
    "Bad Bunny": "Puerto Rico",
    "Adele": "United Kingdom",
    "BTS": "South Korea",
    "BLACKPINK": "South Korea",
    "Daft Punk": "France",
    "Arctic Monkeys": "United Kingdom",
    "The Beatles": "United Kingdom",
    "Kendrick Lamar": "United States",
    "YOASOBI": "Japan",
    "IU": "South Korea",
    "Rammstein": "Germany",
}

MB_COUNTRY_CACHE: Dict[str, Optional[str]] = {}

# -------------- helpers --------------
def region_of(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    return COUNTRY_TO_REGION.get(country)

def rollup_regions(country_counts: Dict[str, int]) -> Dict[str, float]:
    total = sum(country_counts.values())
    if total == 0:
        return {}
    reg_counts: Dict[str, int] = {}
    for country, cnt in country_counts.items():
        reg = region_of(country) or "Unknown"
        reg_counts[reg] = reg_counts.get(reg, 0) + cnt
    return {reg: cnt / total for reg, cnt in reg_counts.items()}

def mb_lookup_country(artist_name: str) -> Optional[str]:
    """Optional MusicBrainz lookup (disabled by default for speed)."""
    if not USE_MB:
        return None
    if artist_name in MB_COUNTRY_CACHE:
        return MB_COUNTRY_CACHE[artist_name]

    try:
        url = "https://musicbrainz.org/ws/2/artist"
        params = {"query": f'artist:"{artist_name}"', "limit": 1, "fmt": "json"}
        headers = {"User-Agent": "TuniverseDemo/1.0 (class project)"}
        r = requests.get(url, params=params, headers=headers, timeout=3.0)
        r.raise_for_status()
        data = r.json()
        if data.get("artists"):
            a = data["artists"][0]
            if a.get("country"):
                MB_COUNTRY_CACHE[artist_name] = a["country"]
                return a["country"]
            for key in ("area", "begin-area"):
                area = a.get(key)
                if isinstance(area, dict) and area.get("name"):
                    MB_COUNTRY_CACHE[artist_name] = area["name"]
                    return area["name"]
    except Exception:
        pass

    MB_COUNTRY_CACHE[artist_name] = None
    return None

def infer_country_fast(artist_name: str) -> str:
    if artist_name in QUICK_COUNTRY_SEEDS:
        return QUICK_COUNTRY_SEEDS[artist_name]
    c = mb_lookup_country(artist_name)
    return c or "Unknown"

def _spotify_get(path: str, access_token: str, params: Optional[Dict] = None):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.spotify.com/v1{path}"
    r = requests.get(url, headers=headers, params=params or {}, timeout=8)
    if r.status_code == 401:
        return {"error": "unauthorized"}
    try:
        return r.json()
    except Exception:
        return {"error": f"bad json ({r.status_code})"}

# -------------- DB-based (original) --------------
@router.get("/{user_id}", response_model=PassportSummaryOut)
def get_passport(user_id: str, db: Session = Depends(get_db)):
    tracks: List[models.Track] = (
        db.query(models.Track)
          .join(models.Playlist)
          .filter(models.Playlist.user_id == user_id)
          .all()
    )
    artist_ids = set()
    for t in tracks:
        for aid in (t.artist_ids or []):
            artist_ids.add(aid)

    if artist_ids:
        artists: List[models.Artist] = (
            db.query(models.Artist)
              .filter(models.Artist.spotify_artist_id.in_(list(artist_ids)))
              .all()
        )
    else:
        artists = []

    country_counts: Dict[str, int] = {}
    for a in artists:
        c = a.origin_country or "Unknown"
        country_counts[c] = country_counts.get(c, 0) + 1

    total = len(artists)
    region_percentages = rollup_regions(country_counts)
    passport = crud.create_passport(db, user_id, country_counts, region_percentages, total)
    return passport

# -------------- Live from Spotify: Top Artists --------------
@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(10, ge=1, le=50),
):
    top = _spotify_get("/me/top/artists", access_token, params={"limit": limit})
    items = top.get("items", []) if isinstance(top, dict) else []
    if not items:
        return {
            "id": "live-top-empty",
            "user_id": "from_token",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "country_counts": {},
            "region_percentages": {},
            "total_artists": 0,
            "note": "No top artists returned by Spotify."
        }

    country_counts: Dict[str, int] = {}
    for a in items:
        name = (a or {}).get("name")
        if not name:
            continue
        c = infer_country_fast(name)
        country_counts[c] = country_counts.get(c, 0) + 1

    return {
        "id": "live-top",
        "user_id": "from_token",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
        "total_artists": len(items),
    }

# -------------- Live from Spotify: Recently Played --------------
@router.get("/from_recent")
def passport_from_recent(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(30, ge=1, le=50),
):
    recent = _spotify_get("/me/player/recently-played", access_token, params={"limit": limit})
    items = recent.get("items", []) if isinstance(recent, dict) else []
    if not items:
        return {
            "id": "live-recent-empty",
            "user_id": "from_recent",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "country_counts": {},
            "region_percentages": {},
            "total_artists": 0,
            "note": "No recent plays returned by Spotify."
        }

    names: List[str] = []
    seen = set()
    for it in items:
        tr = (it or {}).get("track") or {}
        for art in tr.get("artists") or []:
            nm = art.get("name")
            if nm and nm not in seen:
                seen.add(nm)
                names.append(nm)
    names = names[:12]  # cap

    country_counts: Dict[str, int] = {}
    for nm in names:
        c = infer_country_fast(nm)
        country_counts[c] = country_counts.get(c, 0) + 1

    return {
        "id": "live-recent",
        "user_id": "from_recent",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
        "total_artists": len(names),
    }

# Exported for community router
__all__ = ["mb_lookup_country", "rollup_regions"]




