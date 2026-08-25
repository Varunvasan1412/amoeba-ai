# ACP v1 FINAL — Do not extend without version bump

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.models.report_registry import ReportRegistry
from app.services.onboarding import discover_tables
import re
import secrets
from app.services.audit_service import log_audit
from app.core.auth_deps import get_current_active_admin

router = APIRouter(dependencies=[Depends(get_current_active_admin)])

class RegisterReportRequest(BaseModel):
    client_id: int
    report_name: str
    base_table: str
    date_column: Optional[str] = None
    output_format: str = "xlsx"

from app.core.rate_limiter import limiter
from app.core.config import settings

@router.post("/reports")
@limiter.limit(settings.RATE_LIMIT_REPORT)
async def register_report(
    payload: RegisterReportRequest,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Step 4: Register a Report.
    Auto-generates SQL. user CANNOT provide SQL.
    """
    # 1. Validate Client
    client = await session.get(ClientConfig, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
        
    # 2. Validate Table Exists (Security & Sanity)
    # We inspect the DB again to be sure the table exists.
    try:
        schema = discover_tables(client.db_connection_url)
        table_names = [t["name"] for t in schema]
        if payload.base_table not in table_names:
            raise HTTPException(status_code=400, detail=f"Table '{payload.base_table}' does not exist in client database.")
            
        # Validate Date Column if provided
        if payload.date_column:
             target_table = next(t for t in schema if t["name"] == payload.base_table)
             if payload.date_column not in target_table["columns"]:
                 raise HTTPException(status_code=400, detail=f"Column '{payload.date_column}' does not exist in table '{payload.base_table}'.")

    except ValueError:
         raise HTTPException(status_code=400, detail="Could not validate table. Database connection failed.")
    except Exception as e:
         # In production, log internal error but return generic
         print(f"Validation Error: {e}")
         if "Table" in str(e) or "Column" in str(e):
             raise e
         raise HTTPException(status_code=500, detail="Internal validation error")

    # 3. Generate SQL (The ONLY place this happens)
    # Simple SELECT * for now.
    sql_query = f"SELECT * FROM {payload.base_table}"
    
    # 4. Generate Report Key (slugify)
    slug = re.sub(r'[^a-z0-9_]+', '_', payload.report_name.lower()).strip('_')
    
    # 5. Save to Registry
    # Check for duplicate key
    existing = await session.execute(
        select(ReportRegistry).where(
            ReportRegistry.client_id == client.id,
            ReportRegistry.report_key == slug
        )
    )
    if existing.scalars().first():
        slug = f"{slug}_{secrets.token_hex(2)}" # Handle collision

    new_report = ReportRegistry(
        client_id=client.id,
        report_key=slug,
        display_name=payload.report_name,
        sql_template=sql_query,
        date_column=payload.date_column,
        output_format=payload.output_format,
        user_phrases=[f"show {payload.report_name}", f"get {payload.report_name}"]
    )
    
    session.add(new_report)
    await session.commit()
    await session.refresh(new_report)
    
    log_audit(client.id, "report_registered", {
        "report_name": payload.report_name,
        "base_table": payload.base_table,
        "report_key": new_report.report_key
    })
    
    return {
        "status": "success",
        "data": {
            "report_id": new_report.id,
            "report_key": new_report.report_key,
            "sql_generated": sql_query
        }
    }

