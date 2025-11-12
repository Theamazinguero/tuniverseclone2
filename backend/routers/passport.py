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
#  - GET /passport/{user_id}          -> DB-based summary (original flow)
#  - GET /passport/from_token         -> Live snapshot from Spotify Top Artists
#  - GET /passport/from_token_recent  -> Live snapshot from Recently Played

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
import os
import time
import requests

from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

router = APIRouter(prefix="/passport", tags=["Music Passport"])

# ---------------- Region helpers ----------------

COUNTRY_TO_REGION = {
    # long names
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "Ireland": "Europe", "Germany": "Europe", "France": "Europe",
    "Spain": "Europe", "Italy": "Europe", "Netherlands": "Europe", "Sweden": "Europe",
    "Norway": "Europe", "Finland": "Europe", "Denmark": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Russia": "Europe",
    "Japan": "Asia", "South Korea": "Asia", "China": "Asia", "India": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America", "Colombia": "South America",
    "South Africa": "Africa", "Nigeria": "Africa", "Egypt": "Africa",
    # common 2-letter codes
    "US": "North America", "CA": "North America", "MX": "North America",
    "GB": "Europe", "IE": "Europe", "DE": "Europe", "FR": "Europe", "ES": "Europe",
    "IT": "Europe", "NL": "Europe", "SE": "Europe", "NO": "Europe", "FI": "Europe", "DK": "Europe", "PL": "Europe",
    "PT": "Europe", "RU": "Europe",
    "JP": "Asia", "KR": "Asia", "CN": "Asia", "IN": "Asia",
    "AU": "Oceania", "NZ": "Oceania",
    "BR": "South America", "AR": "South America", "CL": "South America", "CO": "South America",
    "ZA": "Africa", "NG": "Africa", "EG": "Africa",
}

QUICK_COUNTRY_SEEDS: Dict[str, str] = {
    # fast demo seeds — add your favorites here
    "Taylor Swift": "United States",
    "Drake": "Canada",
    "Adele": "United Kingdom",
    "Bad Bunny": "Puerto Rico",
    "BTS": "South Korea",
    "BLACKPINK": "South Korea",
    "Arctic Monkeys": "United Kingdom",
    "Daft Punk": "France",
    "YOASOBI": "Japan",
    "Kendrick Lamar": "United States",
}

USE_MB = os.getenv("PASSPORT_USE_MB", "0") == "1"
_MB_CACHE: Dict[str, Optional[str]] = {}

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
    """Optional MusicBrainz lookup; disabled by default for speed."""
    if not USE_MB:
        return None
    if artist_name in _MB_CACHE:
        return _MB_CACHE[artist_name]
    try:
        url = "https://musicbrainz.org/ws/2/artist"
        params = {"query": f'artist:"{artist_name}"', "limit": 1, "fmt": "json"}
        headers = {"User-Agent": "TuniverseDemo/1.0 (class project)"}
        r = requests.get(url, params=params, headers=headers, timeout=3.0)
        r.raise_for_status()
        data = r.json()
        if data.get("artists"):
            a = data["artists"][0]
            if "country" in a:
                _MB_CACHE[artist_name] = a["country"]
                return a["country"]
            for key in ("area", "begin-area"):
                if isinstance(a.get(key), dict) and a[key].get("name"):
                    _MB_CACHE[artist_name] = a[key]["name"]
                    return a[key]["name"]
    except Exception:
        pass
    _MB_CACHE[artist_name] = None
    return None

def infer_country_fast(artist_name: str) -> str:
    if artist_name in QUICK_COUNTRY_SEEDS:
        return QUICK_COUNTRY_SEEDS[artist_name]
    c = mb_lookup_country(artist_name)
    return c or "Unknown"

# ---------------- Original DB-based summary ----------------

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
        artists = (
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

# ---------------- Live snapshots (Spotify token) ----------------

def _sp_get(path: str, access_token: str, params: Optional[Dict] = None):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.spotify.com/v1{path}"
    r = requests.get(url, headers=headers, params=params or {}, timeout=8)
    if r.status_code == 401:
        return {"error": "unauthorized"}
    try:
        return r.json()
    except Exception:
        return {"error": f"bad json ({r.status_code})"}

@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(10, ge=1, le=25),
):
    top = _sp_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(top, dict) or "items" not in top:
        raise HTTPException(status_code=400, detail=f"/me/top/artists failed: {top}")

    country_counts: Dict[str, int] = {}
    total_artists = 0
    for a in top["items"]:
        name = a.get("name")
        if not name:
            continue
        total_artists += 1
        country = infer_country_fast(name)
        country_counts[country] = country_counts.get(country, 0) + 1

    return {
        "id": "from_token_snapshot",
        "user_id": "from_token",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
        "total_artists": total_artists,
    }

@router.get("/from_token_recent")
def passport_from_token_recent(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(20, ge=1, le=50),
):
    recent = _sp_get("/me/player/recently-played", access_token, params={"limit": limit})
    items = recent.get("items", []) if isinstance(recent, dict) else []

    names: List[str] = []
    seen = set()
    for it in items:
        track = (it or {}).get("track") or {}
        artists = track.get("artists") or []
        for a in artists:
            nm = a.get("name")
            if nm and nm not in seen:
                seen.add(nm)
                names.append(nm)
    names = names[:12]

    country_counts: Dict[str, int] = {}
    for nm in names:
        country = infer_country_fast(nm)
        country_counts[country] = country_counts.get(country, 0) + 1

    return {
        "id": "from_recent_snapshot",
        "user_id": "from_token_recent",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
        "total_artists": len(names),
    }





