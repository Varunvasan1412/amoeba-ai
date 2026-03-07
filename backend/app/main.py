from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import chat, upload, navigation, reports, clients, auth, onboarding
from app.core.database import init_db
from app.tools.navigation import load_sitemap

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🐘 Connecting to Database...")
    await init_db()
    
    print("🗺️  Preloading Navigation Sitemap...")
    load_sitemap(refresh=True)
    
    yield
    print("🐘 Database connection closed.")

app = FastAPI(
    title="Amoeba AI API",
    lifespan=lifespan
)

# --- SECURITY PERMISSION (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow React frontend to access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------

from fastapi.staticfiles import StaticFiles
import os

# Ensure static directory exists
os.makedirs("static/reports", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(navigation.router, prefix="/api/navigation")
app.include_router(reports.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(onboarding.router)

# v2 Semantic Layer (Feature Flagged)
ENABLE_SEMANTIC_LAYER = True # In production, use env var
if ENABLE_SEMANTIC_LAYER:
    from app.routers import semantic, builder, relationships, relationships_bulk
    app.include_router(semantic.router, prefix="/api") 
    app.include_router(builder.router, prefix="/api")
    app.include_router(relationships.router, prefix="/api")
    app.include_router(relationships_bulk.router, prefix="/api")


@app.get("/")
def read_root():
    return {"status": "Amoeba AI is active"}