from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.services.builder_service import generate_safe_sql
from app.services.relationship_service import get_relationship_graph
from app.services.audit_service import log_audit
from sqlmodel import select
from app.core.auth_deps import get_current_active_admin
from datetime import datetime
import re

router = APIRouter(
    prefix="/v2/builder", 
    tags=["v2 Visual Builder"],
    dependencies=[Depends(get_current_active_admin)]
)

async def get_client_id_by_key(api_key: str, session: AsyncSession):
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    
    stmt = select(ClientConfig).where(ClientConfig.api_key == api_key)
    result = await session.execute(stmt)
    client = result.scalars().first()
    
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return client.id

def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')

@router.post("/preview")
async def preview_report(
    request: Dict[str, Any],
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Generates SQL and returns a preview of 10 rows.
    """
    client_id = await get_client_id_by_key(x_api_key, session)
    
    # 1. Generate SQL (Deterministic)
    sql_string = await generate_safe_sql(session, client_id, request)
    
    # 2. Execute Preview (LIMIT 10)
    preview_sql = f"SELECT * FROM ({sql_string}) AS sub LIMIT 10"
    
    # Logic to execute against client DB would go here.
    # For now returning the SQL as proof of work.
    
    return {
        "status": "success",
        "generated_sql": sql_string,
        "preview_data": [], 
        "message": "SQL generated successfully."
    }

@router.post("/preview/data")
async def preview_data(
    payload: Dict[str, Any],
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Execute the generated SQL and return preview data (Max 50 rows).
    """
    try:
        client_id = await get_client_id_by_key(x_api_key, session)
        request_dict = payload.get("request", {})
        if not request_dict:
             request_dict = payload

        print(f"DEBUG: Generating SQL for client {client_id}", flush=True)
        # 1. Generate SQL
        sql = await generate_safe_sql(session, client_id, request_dict)
        
        print(f"DEBUG: Executing SQL", flush=True)
        # 2. Get Data
        from app.services.builder_service import execute_safe_sql
        rows = await execute_safe_sql(session, client_id, request_dict)
        
        return {"sql": sql, "data": rows}
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        error_msg = f"Report Builder Error: {str(e)}"
        print(f"ERROR: {error_msg}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/save")
async def save_report(
    payload: Dict[str, Any],
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Saves the report to the registry.
    Input: { "client_id": 1, "report_name": "...", "builder_definition": {...} }
    """
    # Note: client_id in payload is redundant if we check API Key, but we validate match
    api_client_id = await get_client_id_by_key(x_api_key, session)
    
    if payload.get("client_id") and payload["client_id"] != api_client_id:
        raise HTTPException(status_code=403, detail="Client ID mismatch")
    
    report_name = payload["report_name"]
    definition = payload["builder_definition"]
    
    # 1. Generate SQL
    sql_string = await generate_safe_sql(session, api_client_id, definition)
    
    # 2. Save to Report Registry (v1 Model)
    from app.models.report_registry import ReportRegistry
    
    # Generate slug for unique key
    report_key = slugify(report_name)
    
    # Check if report exists
    stmt = select(ReportRegistry).where(
        ReportRegistry.client_id == api_client_id,
        ReportRegistry.report_key == report_key
    )
    result = await session.execute(stmt)
    existing_report = result.scalars().first()
    
    try:
        if existing_report is not None:
            # Update existing
            existing_report.display_name = report_name
            existing_report.sql_template = sql_string
            existing_report.builder_definition = definition # NOW PERSISTED!
            
            existing_report.updated_at = datetime.utcnow()
            session.add(existing_report)
            await session.commit()
            await session.refresh(existing_report)
            new_report = existing_report
        else:
            # Create new
            new_report = ReportRegistry(
                client_id=api_client_id,
                report_key=report_key,
                display_name=report_name,
                sql_template=sql_string,
                builder_definition=definition # NOW PERSISTED!
            )
            session.add(new_report)
            await session.commit()
            await session.refresh(new_report)
    except Exception as e:
        await session.rollback()
        # Handle race condition: if it failed because of duplicate key, try to update instead
        if "unique_client_report" in str(e).lower() or "duplicate key" in str(e).lower():
            # Try one more time to fetch and update
            stmt = select(ReportRegistry).where(
                ReportRegistry.client_id == api_client_id,
                ReportRegistry.report_key == report_key
            )
            result = await session.execute(stmt)
            existing_report = result.scalars().first()
            if existing_report is not None:
                existing_report.display_name = report_name
                existing_report.sql_template = sql_string
                existing_report.builder_definition = definition
                existing_report.updated_at = datetime.utcnow()
                session.add(existing_report)
                await session.commit()
                await session.refresh(existing_report)
                new_report = existing_report
            else:
                raise e
        else:
            raise e
    
    log_audit(api_client_id, "report_built_v2", {"report_id": new_report.id, "name": report_name})
    
    return {
        "status": "success",
        "report_id": new_report.id,
        "sql": sql_string
    }

@router.get("/reports")
async def list_reports(
    client_id: int = None,
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    List all reports for the authenticated client.
    """
    api_client_id = await get_client_id_by_key(x_api_key, session)
    
    # Optional check if query param matches token (not strictly necessary as we use token)
    if client_id and client_id != api_client_id:
         # We could raise 403, or just ignore the query param and use the token's client_id
         pass

    from app.models.report_registry import ReportRegistry
    from sqlmodel import desc
    
    stmt = select(ReportRegistry).where(
        ReportRegistry.client_id == api_client_id
    ).order_by(desc(ReportRegistry.created_at))
    
    result = await session.execute(stmt)
    reports = result.scalars().all()
    
    return {"status": "success", "reports": reports}

@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: int,
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete a report by ID.
    """
    api_client_id = await get_client_id_by_key(x_api_key, session)
    from app.models.report_registry import ReportRegistry
    
    stmt = select(ReportRegistry).where(
        ReportRegistry.id == report_id,
        ReportRegistry.client_id == api_client_id
    )
    result = await session.execute(stmt)
    report = result.scalars().first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    await session.delete(report)
    await session.commit()
    
    return {"status": "success", "message": "Report deleted"}

@router.post("/reports/{report_id}/run")
async def run_report(
    report_id: int,
    payload: Dict[str, Any] = {},
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Executes a saved report and returns a link to the generated Excel file.
    """
    api_client_id = await get_client_id_by_key(x_api_key, session)
    from app.models.report_registry import ReportRegistry
    from app.tools.reporting import export_sql_to_excel
    from app.tools.filenames import generate_deterministic_filename
    from app.core.config import settings
    import os
    from datetime import datetime
    
    stmt = select(ReportRegistry).where(
        ReportRegistry.id == report_id,
        ReportRegistry.client_id == api_client_id
    )
    result = await session.execute(stmt)
    report = result.scalars().first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    sql_query = report.sql_template
    
    # Simple Parameter Replacement (if needed in Phase 3)
    if ":start_date" in sql_query:
        start_date = payload.get("start_date") or "1970-01-01"
        end_date = payload.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        sql_query = sql_query.replace(":start_date", f"'{start_date}'").replace(":end_date", f"'{end_date}'")
        
    try:
        # We need the client config to set the current_db_url context for export_sql_to_excel
        stmt_client = select(ClientConfig).where(ClientConfig.id == api_client_id)
        res_client = await session.execute(stmt_client)
        client_conf = res_client.scalars().first()
        
        from app.core.context import current_db_url
        current_db_url.set(client_conf.db_connection_url)
        
        filename = generate_deterministic_filename(report.display_name, extension="xlsx")
        file_path = export_sql_to_excel(sql_query, filename_override=filename)
        
        if "Error" in file_path:
             raise Exception(file_path)
             
        # Build public URL
        if "static" in file_path:
            clean_path = file_path[file_path.find("static"):].replace(os.path.sep, "/")
            file_url = f"{settings.PUBLIC_BASE_URL}/{clean_path}"
        else:
            file_url = file_path
            
        log_audit(api_client_id, "report_manual_run", {"report_id": report.id})
        
        return {
            "status": "success", 
            "file_url": file_url,
            "message": "Report generated successfully"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to run report: {e}")

from app.services.relationship_service import get_relationship_graph, validate_join_path, clear_relationship_cache

@router.post("/reset-cache")
async def reset_builder_cache(api_key: str = Header(None, alias="X-API-Key"), session: AsyncSession = Depends(get_session)):
    client_id = await get_client_id_by_key(api_key, session)
    clear_relationship_cache(client_id)
    return {"status": "success", "message": "Relationship cache cleared for client"}

@router.get("/relationships")
async def get_relationships(
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Returns the join graph for the authenticated client.
    """
    client_id = await get_client_id_by_key(x_api_key, session)
    graph = await get_relationship_graph(session, client_id)
    return {"status": "success", "graph": graph}
