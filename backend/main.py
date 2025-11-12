"""
Main Code Runner
@Author: Emily Villareal
@Version: 1.0
@Since: 10/03/2025
Usage:
Main to run all the code
Change Log:
Version 1.0 (10/03/2025):
Created main to run backend code
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load env from backend/.env
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except Exception:
    pass

from backend.routers import users, playlists, artists, passport, compare
from backend.routers import demo_passport
from backend import spotify_auth
# Optional community router — leave commented out if not present
# from backend.routers import community

app = FastAPI(title="Tuniverse Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo-friendly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(artists.router, prefix="/artists", tags=["Artists"])
# IMPORTANT: do NOT add a prefix here; the passport router already has /passport
app.include_router(passport.router)   # <- FIXED
app.include_router(compare.router, prefix="/compare", tags=["Comparisons"])
app.include_router(demo_passport.router, tags=["Demo"])
app.include_router(spotify_auth.router, tags=["Auth"])
# app.include_router(community.router, prefix="/community", tags=["Community"])

@app.get("/")
def root():
    return {"message": "Tuniverse backend running"}

