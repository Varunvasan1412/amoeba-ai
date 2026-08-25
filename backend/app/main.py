import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from contextlib import asynccontextmanager
from app.routers import chat, chat_history, upload, navigation, reports, clients, auth, onboarding, ui_schema, ai_settings, admin_validation, documents, system_health, backup, users
from app.core.database import init_db
from app.core.scheduler import start_scheduler, scheduler, CronTrigger
from sqlalchemy import select
from app.core.database import async_session
from app.core.rate_limiter import limiter, rate_limit_reason_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis
from fastapi.responses import JSONResponse

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

    # 🕒 Start Scheduler & Register Backup Job
    start_scheduler()
    async with async_session() as session:
        try:
            from app.models.backup_settings import BackupSettings
            stmt = select(BackupSettings).limit(1)
            res = await session.execute(stmt)
            b_settings = res.scalar_one_or_none()
            
            if not b_settings:
                b_settings = BackupSettings()
                session.add(b_settings)
                await session.commit()
                await session.refresh(b_settings)
            
            from app.services.backup_service import create_backup
            from app.services.backup_validation_service import run_automated_validation
            
            def run_backup():
                # Runs in a separate thread from BackgroundScheduler
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(create_backup())
                loop.close()

            def run_validation():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_automated_validation())
                loop.close()

            scheduler.add_job(
                run_backup,
                CronTrigger(hour=b_settings.schedule_hour, minute=b_settings.schedule_minute),
                id="daily_backup",
                replace_existing=True
            )
            
            # Weekly validation on Sunday at 3:00 AM
            scheduler.add_job(
                run_validation,
                CronTrigger(day_of_week='sun', hour=3, minute=0),
                id="weekly_backup_validation",
                replace_existing=True
            )

            print(f"🕒 Backup scheduled for {b_settings.schedule_hour:02d}:{b_settings.schedule_minute:02d}")
            print(f"🕒 Weekly validation scheduled for Sunday 03:00")
        except Exception as e:
            print(f"❌ Failed to schedule background tasks: {e}")
    
    yield
    print("🐘 Database connection closed.")

app = FastAPI(
    title="Amoeba AI API",
    lifespan=lifespan,
    redirect_slashes=False
)

# --- RATE LIMITING ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_reason_handler)

@app.exception_handler(redis.exceptions.ConnectionError)
async def redis_connection_error_handler(request: Request, exc: redis.exceptions.ConnectionError):
    """
    Handler for Redis connection issues during runtime.
    Note: Dynamic fail-open at startup is handled in rate_limiter.py.
    """
    import logging
    logger = logging.getLogger("app")
    logger.error(f"Rate Limit Storage Error: {exc}. Returning 500 fallback.")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error (Storage Connection)"})

app.add_middleware(SlowAPIMiddleware)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# --- SECURITY PERMISSION (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
app.include_router(backup.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(ui_schema.router, prefix="/api/ui-schema", tags=["UI Learning"])

from app.routers import field_metadata, audit
app.include_router(field_metadata.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(audit.purge_router, prefix="/api")


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
