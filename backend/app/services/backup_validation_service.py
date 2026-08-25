import os
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import text, create_engine
from app.core.config import settings
from app.core.database import async_session
from app.models.backup_validation import BackupValidationLog
from app.services.backup_service import BACKUP_DIR
from urllib.parse import urlparse

async def test_restore(backup_file: str) -> Dict[str, Any]:
    """
    Safely validates a backup by restoring it into a temporary database.
    """
    start_time = time.time()
    filepath = os.path.join(BACKUP_DIR, backup_file)
    
    if not os.path.exists(filepath):
        return {"success": False, "error": "Backup file not found"}

    # Safety check: Size limit (2GB)
    file_size = os.path.getsize(filepath)
    if file_size > 2 * 1024 * 1024 * 1024:
        await _log_validation(backup_file, "SKIPPED", 0, "Backup too large to test (> 2GB)")
        return {"success": False, "error": "Backup too large to test (> 2GB)"}

    test_db_name = "amoeba_restore_test"
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(db_url)
    
    # Connection string for 'postgres' default DB to manage other DBs
    admin_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        # 1. Create temporary database
        with admin_engine.connect() as conn:
            # Terminate any existing connections to the test DB just in case
            conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}'"))
            conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
            conn.execute(text(f"CREATE DATABASE {test_db_name}"))

        # 2. Restore backup into test DB
        env = os.environ.copy()
        env["PGPASSWORD"] = parsed.password
        cmd = [
            "psql",
            "-h", parsed.hostname,
            "-p", str(parsed.port or 5432),
            "-U", parsed.username,
            "-d", test_db_name,
            "-f", filepath
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0) # 5 min timeout for validation
        except asyncio.TimeoutError:
            process.kill()
            raise Exception("Restore timed out during validation")

        if process.returncode != 0:
            raise Exception(f"Restore failed: {stderr.decode()}")

        # 3. Validate Integrity
        test_db_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/{test_db_name}"
        test_engine = create_engine(test_db_url)
        
        validation_errors = []
        with test_engine.connect() as conn:
            # Check for essential tables
            required_tables = ["users", "ai_settings", "backupsettings"]
            for table in required_tables:
                res = conn.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table}')"))
                if not res.scalar():
                    validation_errors.append(f"Missing table: {table}")

            # If core tables exist, do a sanity row count
            if not validation_errors:
                count_res = conn.execute(text("SELECT COUNT(*) FROM ai_settings"))
                if count_res.scalar() == 0:
                    validation_errors.append("Empty ai_settings (unlikely for health DB)")

        if validation_errors:
            raise Exception(" ; ".join(validation_errors))

        # Success!
        duration = int((time.time() - start_time) * 1000)
        await _log_validation(backup_file, "PASS", duration)
        return {"success": True, "message": "Validation passed"}

    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        await _log_validation(backup_file, "FAIL", duration, str(e))
        return {"success": False, "error": str(e)}

    finally:
        # 4. Cleanup
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}'"))
                conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        except:
            pass

async def _log_validation(backup_file: str, status: str, duration: int, error: str = None):
    async with async_session() as session:
        log = BackupValidationLog(
            backup_file=backup_file,
            status=status,
            duration_ms=duration,
            error_message=error,
            tested_at=datetime.now(timezone.utc)
        )
        session.add(log)
        await session.commit()

async def run_automated_validation():
    """
    Finds the latest backup and runs validation on it.
    """
    from app.services.backup_service import list_backups
    backups = await list_backups()
    if not backups:
        return
    
    # Test the most recent one
    latest = backups[0]["file_name"]
    print(f"🕒 Starting automated weekly validation for {latest}")
    await test_restore(latest)
