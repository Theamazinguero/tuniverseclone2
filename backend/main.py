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


# backend/main.py
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load env (so spotify_auth sees your keys from backend/.env)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except Exception:
    # ok to proceed if you set env vars in the shell instead of a .env file
    pass

# Routers (make sure these modules exist; if any is missing, comment that line out temporarily)
from backend.routers import users, playlists, artists, passport, compare
from backend.routers import demo_passport
from backend import spotify_auth  # <-- add this

app = FastAPI(title="Tuniverse Backend")

# CORS (needed for your web-test page)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo-friendly; tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(artists.router, prefix="/artists", tags=["Artists"])
app.include_router(passport.router, prefix="/passport", tags=["Music Passport"])
app.include_router(compare.router, prefix="/compare", tags=["Comparisons"])
# app.include_router(demo_passport.router, tags=["Demo"]) 
app.include_router(spotify_auth.router)  # <-- add this (exposes /auth/login, /auth/callback, etc.)

@app.get("/")
def root():
    return {"message": "Tuniverse backend running"}
