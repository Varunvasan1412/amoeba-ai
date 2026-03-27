import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from contextlib import asynccontextmanager
from app.routers import chat, chat_history, upload, navigation, reports, clients, auth, onboarding, ui_schema, ai_settings, admin_validation, documents, system_health
from app.core.database import init_db
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🐘 Connecting to Database...")
    await init_db()
    
    # 🧹 Start Background Cleanup Service
    from app.services.cleanup_service import cleanup_loop
    asyncio.create_task(cleanup_loop())
    
    # 📈 Start Daily Usage Logger (Step 7)
    from app.services.usage_service import usage_logger_loop
    asyncio.create_task(usage_logger_loop())
    
    yield
    print("🐘 Database connection closed.")

app = FastAPI(
    title="Amoeba AI API",
    lifespan=lifespan,
    redirect_slashes=False
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# --- SECURITY PERMISSION (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/reports", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Unified API prefix handling
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(chat_history.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(navigation.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(ai_settings.router, prefix="/api")
app.include_router(admin_validation.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(system_health.router, prefix="/api")
app.include_router(ui_schema.router, prefix="/api/ui-schema", tags=["UI Learning"])

from app.routers import field_metadata
app.include_router(field_metadata.router, prefix="/api")

# v2 Semantic Layer
ENABLE_SEMANTIC_LAYER = True
if ENABLE_SEMANTIC_LAYER:
    from app.routers import semantic, builder, relationships, relationships_bulk
    app.include_router(semantic.router, prefix="/api") 
    app.include_router(builder.router, prefix="/api")
    app.include_router(relationships.router, prefix="/api")
    app.include_router(relationships_bulk.router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "Amoeba AI is active"}
