# backend/routers/community.py
"""
Community sharing router (demo-friendly):
- POST /community/aggregate_from_tokens
  Body: {"tokens": ["spot_access_token_1", "spot_access_token_2", ...], "limit": 12}
  Returns one aggregated Music Passport built live from each member's Top Artists.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict

# Re-use helpers from the passport module
try:
    from .passport import mb_lookup_country, rollup_regions
except Exception:
    # If import path differs, adjust as needed
    from backend.routers.passport import mb_lookup_country, rollup_regions  # type: ignore

# Spotify GET helper
try:
    from ..spotify_client import spotify_get
except Exception:
    from backend.spotify_client import spotify_get  # type: ignore

router = APIRouter()

class TokensIn(BaseModel):
    tokens: List[str] = Field(default_factory=list, description="Spotify access tokens of group members")
    limit: int = Field(12, ge=1, le=50, description="How many top artists to fetch per member")

@router.post("/aggregate_from_tokens")
def aggregate_from_tokens(req: TokensIn):
    if not req.tokens:
        raise HTTPException(status_code=400, detail="No tokens provided")

    agg_country_counts: Dict[str, int] = {}
    total_artists = 0

    for idx, token in enumerate(req.tokens, start=1):
        top = spotify_get("/me/top/artists", token, params={"limit": req.limit})
        if not isinstance(top, dict) or "items" not in top:
            # Skip this member but continue aggregating others
            continue

        for artist in top.get("items", []):
            name = (artist or {}).get("name")
            if not name:
                continue
            total_artists += 1
            country = mb_lookup_country(name) or "Unknown"
            agg_country_counts[country] = agg_country_counts.get(country, 0) + 1

    region_percentages = rollup_regions(agg_country_counts)

    return {
        "group_size": len(req.tokens),
        "total_artists": total_artists,
        "country_counts": agg_country_counts,
        "region_percentages": region_percentages,
        "note": "Aggregated from members' Top Artists (live).",
    }
