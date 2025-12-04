from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import chat
from app.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🐘 Connecting to Database...")
    await init_db()
    yield
    print("🐘 Database connection closed.")

app = FastAPI(lifespan=lifespan)

# --- SECURITY PERMISSION (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow React frontend to access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------

app.include_router(chat.router)

@app.get("/")
def read_root():
    return {"status": "Amoeba AI is active"}