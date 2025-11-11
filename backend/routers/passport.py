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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional, Set
import os, time, requests

from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

# If you have a spotify helper:
try:
    from ..spotify_client import spotify_get
except Exception:
    from backend.spotify_client import spotify_get  # type: ignore

router = APIRouter()

# --- Country -> Region map (minimal; extend as needed) ---
COUNTRY_TO_REGION = {
    "United States": "North America", "USA": "North America", "U.S.": "North America",
    "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "UK": "Europe", "Ireland": "Europe", "Germany": "Europe",
    "France": "Europe", "Spain": "Europe", "Italy": "Europe", "Netherlands": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Finland": "Europe", "Denmark": "Europe",
    "Poland": "Europe", "Portugal": "Europe", "Russia": "Europe",
    "Japan": "Asia", "South Korea": "Asia", "Korea, Republic of": "Asia", "China": "Asia", "India": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America", "Colombia": "South America",
    "South Africa": "Africa", "Nigeria": "Africa", "Egypt": "Africa",
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

# Best-effort MusicBrainz country lookup (safe fallback = "Unknown")
def mb_lookup_country(artist_name: str) -> Optional[str]:
    try:
        url = "https://musicbrainz.org/ws/2/artist"
        params = {"query": f'artist:"{artist_name}"', "limit": 1, "fmt": "json"}
        headers = {"User-Agent": "TuniverseDemo/1.0 (class project)"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("artists"):
            a = data["artists"][0]
            if "country" in a and a["country"]:
                return a["country"]
            for key in ("area", "begin-area"):
                if isinstance(a.get(key), dict):
                    nm = a[key].get("name")
                    if nm:
                        return nm
    except Exception:
        return None
    finally:
        time.sleep(0.5)  # gentle on MB
    return None

# ------------------- DB-based passport (your original) -------------------
@router.get("/{user_id}", response_model=PassportSummaryOut)
def get_passport(user_id: str, db: Session = Depends(get_db)):
    tracks = (
        db.query(models.Track)
          .join(models.Playlist)
          .filter(models.Playlist.user_id == user_id)
          .all()
    )
    artist_ids: Set[str] = set()
    for t in tracks:
        for aid in (t.artist_ids or []):
            artist_ids.add(aid)

    artists = []
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

# ------------------- Live: from Top Artists -------------------
@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(10, ge=1, le=50),
):
    top = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(top, dict) or "items" not in top:
        raise HTTPException(400, detail=f"Could not fetch top artists: {top}")

    items = top.get("items", [])
    total_artists = len(items)
    country_counts: Dict[str, int] = {}

    for artist in items:
        name = artist.get("name")
        if not name:
            continue
        country = mb_lookup_country(name) or "Unknown"
        country_counts[country] = country_counts.get(country, 0) + 1

    # Guarantee non-empty totals if items exist
    if total_artists > 0 and sum(country_counts.values()) == 0:
        country_counts["Unknown"] = total_artists

    region_percentages = rollup_regions(country_counts)
    return {
        "id": "from_token",
        "user_id": "spotify_user",
        "created_at": None,
        "country_counts": country_counts,
        "region_percentages": region_percentages,
        "total_artists": total_artists,
    }

# ------------------- Live: from Recently Played (fallback) -------------------
@router.get("/from_recent")
def passport_from_recent(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(20, ge=1, le=50),
):
    recent = spotify_get("/me/player/recently-played", access_token, params={"limit": limit})
    if not isinstance(recent, dict) or "items" not in recent:
        raise HTTPException(400, detail=f"Could not fetch recently played: {recent}")

    items = recent.get("items", [])
    # Collect unique artist names from recent plays
    names: Set[str] = set()
    for it in items:
        track = (it or {}).get("track") or {}
        for a in (track.get("artists") or []):
            if a.get("name"):
                names.add(a["name"])

    total_artists = len(names)
    country_counts: Dict[str, int] = {}
    for name in names:
        country = mb_lookup_country(name) or "Unknown"
        country_counts[country] = country_counts.get(country, 0) + 1

    if total_artists > 0 and sum(country_counts.values()) == 0:
        country_counts["Unknown"] = total_artists

    region_percentages = rollup_regions(country_counts)
    return {
        "id": "from_recent",
        "user_id": "spotify_user",
        "created_at": None,
        "country_counts": country_counts,
        "region_percentages": region_percentages,
        "total_artists": total_artists,
    }

