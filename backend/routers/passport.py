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
# Generate music passport summaries:
#  - /passport/{user_id}        -> uses your DB (unchanged behavior)
#  - /passport/from_token       -> builds a live snapshot from Spotify token (no DB write)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional
import os
import time
import requests

# --- your existing imports ---
from ..db import get_db
from .. import crud, models
from ..schemas import PassportSummaryOut

# Use your local spotify helper (relative import preferred inside package)
try:
    from ..spotify_client import spotify_get
except Exception:
    # fallback if package import path differs
    from backend.spotify_client import spotify_get  # type: ignore

router = APIRouter()

# ------------------- helpers for region rollup + MB lookup -------------------

# Minimal country -> region map (extend as needed)
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
    if not country:
        return None
    return COUNTRY_TO_REGION.get(country)

def mb_lookup_country(artist_name: str) -> Optional[str]:
    """
    Best-effort MusicBrainz lookup to infer an artist's country.
    We sleep 1s per call to respect MB rate limits.
    """
    try:
        url = "https://musicbrainz.org/ws/2/artist"
        params = {"query": f'artist:"{artist_name}"', "limit": 1, "fmt": "json"}
        headers = {"User-Agent": "TuniverseDemo/1.0 (class project)"}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        if data.get("artists"):
            a = data["artists"][0]
            if "country" in a:
                return a["country"]
            for key in ("area", "begin-area"):
                if isinstance(a.get(key), dict):
                    nm = a[key].get("name")
                    if nm:
                        return nm
    except Exception:
        return None
    finally:
        time.sleep(1.0)
    return None

def rollup_regions(country_counts: Dict[str, int]) -> Dict[str, float]:
    total = sum(country_counts.values())
    if total == 0:
        return {}
    reg_counts: Dict[str, int] = {}
    for country, cnt in country_counts.items():
        reg = region_of(country) or "Unknown"
        reg_counts[reg] = reg_counts.get(reg, 0) + cnt
    return {reg: cnt / total for reg, cnt in reg_counts.items()}

# ------------------- YOUR EXISTING DB-BASED ENDPOINT (kept) -------------------

@router.get("/{user_id}", response_model=PassportSummaryOut)
def get_passport(user_id: str, db: Session = Depends(get_db)):
    """
    Generate (or fetch latest) music passport summary for user from the DB.
    """
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

    # Your original code put percentages per country; switching to proper region rollup:
    region_percentages = rollup_regions(country_counts)

    passport = crud.create_passport(db, user_id, country_counts, region_percentages, total)

    # Image stub path (keep your existing behavior)
    image_path = os.path.join("share_images", f"passport_{passport.id}.png")
    # TODO: render_passport_image(passport, image_path)

    return passport

# LIVE PASSPORT FROM SPOTIFY TOKEN

@router.get("/from_token")
def passport_from_token(
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(12, ge=1, le=50),
):
    """
    Build a live Music Passport from the user's Spotify top artists.
    Does NOT write to DB; returns an ad-hoc snapshot for the UI.
    """
    top = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(top, dict) or "items" not in top:
        raise HTTPException(status_code=400, detail=f"Could not fetch top artists: {top}")

    country_counts: Dict[str, int] = {}
    total_artists = 0

    for artist in top["items"]:
        name = artist.get("name")
        if not name:
            continue
        total_artists += 1
        country = mb_lookup_country(name) or "Unknown"
        country_counts[country] = country_counts.get(country, 0) + 1

    region_percentages = rollup_regions(country_counts)

    return {
        "user_id": "spotify_user",
        "total_artists": total_artists,
        "country_counts": country_counts,
        "region_percentages": region_percentages,
        "note": "Country via MusicBrainz lookup; approximate and rate-limited for demo.",
    }

