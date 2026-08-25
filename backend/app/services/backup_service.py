import os
import subprocess
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy import text
from app.core.config import settings
from app.core.database import async_session

BACKUP_DIR = "/backups"

async def create_backup() -> Dict[str, Any]:
    """
    Executes pg_dump and stores it in /backups
    """
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)

        filename = f"backup_{datetime.now().strftime('%Y_%m_%d_%H_%M')}.sql"
        filepath = os.path.join(BACKUP_DIR, filename)

        # Build pg_dump command
        # Parsing DATABASE_URL to get credentials (postgresql://user:password@host:port/db)
        from urllib.parse import urlparse
        # settings.DATABASE_URL might be asyncpg (postgresql+asyncpg://...)
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(db_url)
        
        env = os.environ.copy()
        env["PGPASSWORD"] = parsed.password

        cmd = [
            "pg_dump",
            "-h", parsed.hostname,
            "-p", str(parsed.port or 5432),
            "-U", parsed.username,
            "-d", parsed.path.lstrip("/"),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "-f", filepath
        ]

        # Run synchronously for dump (fast enough for now, or use asyncio.create_subprocess_exec)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"success": False, "error": stderr.decode()}

        # Cleanup old backups
        await cleanup_old_backups()

        return {
            "success": True,
            "filename": filename,
            "size": os.path.getsize(filepath),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

async def restore_backup(filename: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Restores database from a given SQL dump.
    """
    if not confirm:
        return {"success": False, "error": "Restore was not confirmed."}

    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"Backup file {filename} not found."}

    try:
        from urllib.parse import urlparse
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(db_url)
        
        env = os.environ.copy()
        env["PGPASSWORD"] = parsed.password

        # Terminate all other connections to the database to avoid locks during psql -f (which drops tables)
        db_name = parsed.path.lstrip("/")
        async with async_session() as session:
            try:
                # We use a raw SQL command to kill other PIDs
                # We skip pg_backend_pid() which is OUR current connection
                # BUT wait! If we are running in a pool, we might kill other workers.
                # That's fine, SQLAlchemy will reconnect them.
                await session.execute(text(f"""
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE datname = '{db_name}' 
                    AND pid <> pg_backend_pid();
                """))
                await session.commit()
            except Exception as e:
                # If this fails, we log it but still try the restore (maybe we don't have superuser but pg_dump/psql might work)
                print(f"⚠️ Warning: Could not terminate other connections: {e}")

        # To restore, we might need to drop everything in public schema or use --clean in pg_dump
        # For simplicity in this implementation, we run psql.
        # Note: A real production restore would handle active connections.
        
        cmd = [
            "psql",
            "-h", parsed.hostname,
            "-p", str(parsed.port or 5432),
            "-U", parsed.username,
            "-d", parsed.path.lstrip("/"),
            "-f", filepath
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            process.kill()
            return {"success": False, "error": "Restore timed out after 60 seconds. This might be due to active database locks. Please try again after a few moments."}

        if process.returncode != 0:
            return {"success": False, "error": stderr.decode()}

        # Update last restore metadata
        try:
            async with async_session() as session:
                from app.models.backup_settings import BackupSettings
                from sqlalchemy import select
                stmt = select(BackupSettings).limit(1)
                res = await session.execute(stmt)
                b_settings = res.scalar_one_or_none()
                if b_settings:
                    b_settings.last_restore_at = datetime.now(timezone.utc).isoformat()
                    b_settings.last_restore_file = filename
                    session.add(b_settings)
                    await session.commit()
        except Exception as e:
            print(f"⚠️ Warning: Could not update restore metadata: {e}")

        return {"success": True, "message": "Restore completed successfully"}

    except Exception as e:
        return {"success": False, "error": str(e)}

async def list_backups() -> List[Dict[str, Any]]:
    """
    Lists all available backup files with metadata.
    """
    if not os.path.exists(BACKUP_DIR):
        return []

    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".sql")]
    backups = []
    
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        stats = os.stat(path)
        # Use UTC for backends
        backups.append({
            "file_name": f,
            "created_at": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
            "file_size": stats.st_size,
            "status": "READY"
        })

    # Sort newest first
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups

async def cleanup_old_backups(max_keep: int = 7):
    """
    Deletes older backups to maintain a history of exactly max_keep.
    """
    if not os.path.exists(BACKUP_DIR):
        return

    files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".sql")]
    files.sort(key=os.path.getctime, reverse=True)

    if len(files) > max_keep:
        for old_file in files[max_keep:]:
            try:
                os.remove(old_file)
            except:
                pass

async def delete_backup(filename: str) -> bool:
    """
    Manually deletes a backup file.
    """
    filepath = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

async def inspect_backup(filename: str) -> Dict[str, Any]:
    """
    Parses the SQL file to find table names and rough metadata.
    """
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": "File not found"}

    try:
        tables = []
        # We'll read only a portion of the file for inspection if it's huge
        # But for AI-driven apps, we want a table list.
        import re
        table_pattern = re.compile(r'CREATE TABLE (?:IF NOT EXISTS )?public\."?(\w+)"?', re.IGNORECASE)
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            # For speed, check first 5000 lines
            for _ in range(5000):
                line = f.readline()
                if not line: break
                match = table_pattern.search(line)
                if match:
                    tables.append(match.group(1))
        
        return {
            "success": True,
            "filename": filename,
            "tables": sorted(list(set(tables))),
            "table_count": len(set(tables))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
