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
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import users, playlists, artists, passport, compare
from backend.routers import demo_passport  # ← add this if you have demo_passport.py

app = FastAPI(title="Tuniverse Backend")

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo-friendly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(artists.router, prefix="/artists", tags=["Artists"])
app.include_router(passport.router, prefix="/passport", tags=["Music Passport"])
app.include_router(compare.router, prefix="/compare", tags=["Comparisons"])
app.include_router(demo_passport.router, tags=["Demo"])  # ← add this

