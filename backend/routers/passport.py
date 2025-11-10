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
#   GET /passport/{user_id}      -> (your original DB-based summary) optional
#   GET /passport/from_token     -> live snapshot from Top Artists (no DB write)
#   GET /passport/from_recent    -> live snapshot from Recently Played (no DB write)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional, Set

from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

try:
    from ..spotify_client import spotify_get
except Exception:
    from backend.spotify_client import spotify_get  # type: ignore

router = APIRouter()

# Minimal country -> region mapping (extend as needed)
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
}

def region_of(country: Optional[str]) -> Optional[str]:
    return COUNTRY_TO_REGION.get(country) if country else None

def rollup_regions(country_counts: Dict[str, int]) -> Dict[str, float]:
    total = sum(country_counts.values())
    if total == 0:
        return {}
    reg_counts: Dict[str, int] = {}
    for country, cnt in country_counts.items():
        reg = region_of(country) or "Unknown"
        reg_counts[reg] = reg_counts.get(reg, 0) + cnt
    return {reg: cnt / total for reg, cnt in reg_counts.items()}


# ---------------- Existing DB-based endpoint (leave as-is if you use it) ----------------
@router.get("/{user_id}", response_model=PassportSummaryOut)
def get_passport(user_id: str, db: Session = Depends(get_db)):
    tracks = (
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


# ---------------- Live from Top Artists (no DB write) ----------------
@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(...),
    limit: int = Query(12, ge=1, le=50),
):
    top = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(top, dict) or "items" not in top:
        return {"user_id": "from_token", "total_artists": 0, "country_counts": {}, "region_percentages": {}}

    # Simple: count artists; country is Unknown for demo speed
    total_artists = 0
    country_counts: Dict[str, int] = {}
    for artist in top.get("items", []):
        if not artist:
            continue
        total_artists += 1
        country_counts["Unknown"] = country_counts.get("Unknown", 0) + 1

    return {
        "user_id": "from_token",
        "total_artists": total_artists,
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
    }


# ---------------- Live from Recently Played (fallback) ----------------
@router.get("/from_recent")
def passport_from_recent(
    access_token: str = Query(...),
    limit: int = Query(50, ge=1, le=50),
):
    rec = spotify_get("/me/player/recently-played", access_token, params={"limit": limit})
    if not isinstance(rec, dict) or "items" not in rec:
        return {"user_id": "from_recent", "total_artists": 0, "country_counts": {}, "region_percentages": {}}

    unique_artist_ids: Set[str] = set()
    for item in rec.get("items", []):
        track = (item or {}).get("track") or {}
        for a in track.get("artists") or []:
            if a and a.get("id"):
                unique_artist_ids.add(a["id"])

    total_artists = len(unique_artist_ids)
    country_counts: Dict[str, int] = {}
    for _ in unique_artist_ids:
        country_counts["Unknown"] = country_counts.get("Unknown", 0) + 1

    return {
        "user_id": "from_recent",
        "total_artists": total_artists,
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
    }
