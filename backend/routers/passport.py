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
# Music Passport endpoints (working rollback):
#  - GET /passport/{user_id}          -> DB-based summary (unchanged)
#  - GET /passport/from_token         -> Live snapshot from Spotify Top Artists
#  - GET /passport/from_token_recent  -> Live snapshot from Recently Played

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
import time
import requests

from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

router = APIRouter(prefix="/passport", tags=["Music Passport"])

COUNTRY_TO_REGION = {
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "Ireland": "Europe", "Germany": "Europe", "France": "Europe",
    "Spain": "Europe", "Italy": "Europe", "Netherlands": "Europe", "Sweden": "Europe",
    "Norway": "Europe", "Finland": "Europe", "Denmark": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Russia": "Europe",
    "Japan": "Asia", "South Korea": "Asia", "China": "Asia", "India": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America", "Colombia": "South America",
    "South Africa": "Africa", "Nigeria": "Africa", "Egypt": "Africa",
    # 2-letter codes
    "US": "North America", "CA": "North America", "GB": "Europe", "FR": "Europe",
    "DE": "Europe", "ES": "Europe", "IT": "Europe", "SE": "Europe",
    "JP": "Asia", "KR": "Asia", "CN": "Asia", "IN": "Asia",
    "AU": "Oceania", "NZ": "Oceania",
    "BR": "South America", "AR": "South America", "CL": "South America", "CO": "South America",
    "ZA": "Africa", "NG": "Africa", "EG": "Africa",
}

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

# ---- DB path (unchanged) ----
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

    artists: List[models.Artist] = []
    if artist_ids:
        artists = (
            db.query(models.Artist)
              .filter(models.Artist.spotify_artist_id.in_(list(artist_ids)))
              .all()
        )

    country_counts: Dict[str, int] = {}
    for a in artists:
        c = a.origin_country or "Unknown"
        country_counts[c] = country_counts.get(c, 0) + 1

    total = len(artists)
    region_percentages = rollup_regions(country_counts)
    passport = crud.create_passport(db, user_id, country_counts, region_percentages, total)
    return passport

# ---- Spotify helpers (simple, local) ----
def spotify_get(path: str, access_token: str, params: Optional[Dict] = None):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.spotify.com/v1{path}"
    r = requests.get(url, headers=headers, params=params or {}, timeout=8)
    try:
        data = r.json()
    except Exception:
        data = {"error": f"bad json ({r.status_code})"}
    if r.status_code == 401:
        return {"error": 401, "text": r.text}
    return data

# ---- Live snapshots (Top Artists / Recently Played) ----
SEED_COUNTRIES: Dict[str, str] = {
    "Taylor Swift": "United States", "Drake": "Canada", "Bad Bunny": "Puerto Rico",
    "Adele": "United Kingdom", "BTS": "South Korea", "BLACKPINK": "South Korea",
    "Daft Punk": "France", "Arctic Monkeys": "United Kingdom", "The Beatles": "United Kingdom",
    "Kendrick Lamar": "United States", "YOASOBI": "Japan", "IU": "South Korea", "Rammstein": "Germany",
}

def infer_country_fast(name: str) -> str:
    return SEED_COUNTRIES.get(name, "Unknown")

@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(10, ge=1, le=20),
):
    top = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(top, dict) or "items" not in top:
        raise HTTPException(status_code=400, detail=f"/me/top/artists failed: {top}")

    country_counts: Dict[str, int] = {}
    total = 0
    for a in top["items"]:
        nm = a.get("name")
        if not nm:
            continue
        total += 1
        c = infer_country_fast(nm)
        country_counts[c] = country_counts.get(c, 0) + 1

    regions = rollup_regions(country_counts)
    return {
        "id": "from_token_snapshot",
        "user_id": "from_token",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": regions,
        "total_artists": total,
    }

@router.get("/from_token_recent")
def passport_from_token_recent(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(20, ge=1, le=50),
):
    recent = spotify_get("/me/player/recently-played", access_token, params={"limit": limit})
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
        c = infer_country_fast(nm)
        country_counts[c] = country_counts.get(c, 0) + 1

    regions = rollup_regions(country_counts)
    return {
        "id": "from_recent_snapshot",
        "user_id": "from_token_recent",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "country_counts": country_counts,
        "region_percentages": regions,
        "total_artists": len(names),
    }




