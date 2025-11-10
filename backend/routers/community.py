# backend/routers/community.py
# Simple in-memory "community sharing" demo:
# - POST /community/create?name=ClassA            -> returns a join code
# - POST /community/join/{code}?access_token=...  -> adds this user's snapshot from Spotify
# - GET  /community/{code}                        -> returns aggregated passport for the group
#
# Notes:
# - This is demo-only (in-memory). Restarting the server clears communities.
# - We count artists but mark country as "Unknown" for speed. You can wire in
#   real country inference later if you want (e.g., via MusicBrainz).
#
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Set
import secrets
import time

try:
    # our local Spotify API helper
    from ..spotify_client import spotify_get
except Exception:
    from backend.spotify_client import spotify_get  # type: ignore

# Import ONLY rollup_regions from passport (do NOT import mb_lookup_country)
try:
    from .passport import rollup_regions
except Exception:
    # fallback minimal region roll-up (all unknown -> 100% Unknown)
    def rollup_regions(country_counts: Dict[str, int]) -> Dict[str, float]:
        total = sum(country_counts.values())
        return {"Unknown": 1.0} if total > 0 else {}

router = APIRouter()

# ---------------- In-memory store (demo) ----------------
# Structure:
# communities = {
#   "ABCD12": {
#       "name": "Class A",
#       "created_at": 1699999999.0,
#       "members": [
#           {
#               "spotify_id": "abc",
#               "display_name": "Alice",
#               "snapshot": {
#                   "total_artists": 12,
#                   "country_counts": {...},
#                   "region_percentages": {...}
#               }
#           }, ...
#       ]
#   },
#   ...
# }
communities: Dict[str, Dict] = {}

def _new_code() -> str:
    # short join code
    return secrets.token_urlsafe(4).replace("-", "").replace("_", "").upper()

# ---------------- Helpers ----------------

def _snapshot_from_top_artists(access_token: str, limit: int = 12) -> Dict:
    """
    Build a quick snapshot from Spotify Top Artists.
    Country is marked as "Unknown" for this demo to keep it fast and reliable.
    """
    data = spotify_get("/me/top/artists", access_token, params={"limit": limit})
    if not isinstance(data, dict) or "items" not in data:
        # Return an empty snapshot so UI still renders
        return {"total_artists": 0, "country_counts": {}, "region_percentages": {}}

    total = 0
    country_counts: Dict[str, int] = {}
    for artist in data.get("items", []):
        if not artist:
            continue
        total += 1
        country_counts["Unknown"] = country_counts.get("Unknown", 0) + 1

    return {
        "total_artists": total,
        "country_counts": country_counts,
        "region_percentages": rollup_regions(country_counts),
    }

def _me_min(access_token: str) -> Dict[str, Optional[str]]:
    me = spotify_get("/me", access_token)
    if not isinstance(me, dict) or "id" not in me:
        return {"id": None, "display_name": None}
    return {"id": me.get("id"), "display_name": me.get("display_name")}

# ---------------- Endpoints ----------------

@router.post("/community/create")
def community_create(name: str = Query(..., min_length=2, max_length=64)):
    code = _new_code()
    communities[code] = {"name": name, "created_at": time.time(), "members": []}
    return {"code": code, "name": name}

@router.post("/community/join/{code}")
def community_join(
    code: str,
    access_token: str = Query(..., description="Spotify access token"),
    limit: int = Query(12, ge=1, le=50),
):
    comm = communities.get(code)
    if not comm:
        raise HTTPException(status_code=404, detail="Community code not found")

    who = _me_min(access_token)
    if not who.get("id"):
        raise HTTPException(status_code=400, detail="Invalid access token or Spotify /me failed")

    snap = _snapshot_from_top_artists(access_token, limit=limit)

    # Deduplicate by spotify_id (if user rejoins, replace their old snapshot)
    existing: List[Dict] = comm["members"]
    # Remove previous entry for same spotify_id
    comm["members"] = [m for m in existing if m.get("spotify_id") != who["id"]]
    # Add new
    comm["members"].append({
        "spotify_id": who["id"],
        "display_name": who["display_name"],
        "snapshot": snap,
    })

    return {"ok": True, "code": code, "members": len(comm["members"])}

@router.get("/community/{code}")
def community_get(code: str):
    comm = communities.get(code)
    if not comm:
        raise HTTPException(status_code=404, detail="Community code not found")

    # Aggregate snapshots
    agg_countries: Dict[str, int] = {}
    total_artists = 0
    for m in comm["members"]:
        snap = m.get("snapshot") or {}
        total_artists += int(snap.get("total_artists") or 0)
        for c, cnt in (snap.get("country_counts") or {}).items():
            agg_countries[c] = agg_countries.get(c, 0) + int(cnt or 0)

    regions = rollup_regions(agg_countries)
    return {
        "code": code,
        "name": comm["name"],
        "members": [
            {
                "spotify_id": m.get("spotify_id"),
                "display_name": m.get("display_name"),
                "total_artists": (m.get("snapshot") or {}).get("total_artists", 0),
            }
            for m in comm["members"]
        ],
        "group_passport": {
            "total_artists": total_artists,
            "country_counts": agg_countries,
            "region_percentages": regions,
        },
    }

