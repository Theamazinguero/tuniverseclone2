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
from fastapi import FastAPI
from .db import Base, engine
from .routers import users, playlists, artists, passport, compare
from .routers import demo_passport #newline 10/14
from . import spotify_auth

app = FastAPI(title="Tuniverse Backend")

# DB init
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(artists.router, prefix="/artists", tags=["Artists"])
app.include_router(passport.router, prefix="/passport", tags=["Music Passport"])
app.include_router(compare.router, prefix="/compare", tags=["Comparisons"])
app.include_router(demo_passport.router, prefix="/demo_passport", tags=["Demo"]) #10/14
app.include_router(spotify_auth.router)

@app.get("/")
def root():
    return {"message": "Tuniverse backend running"}

