from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from datetime import datetime
from app.models.report_registry import ReportRegistry

async def register_reports(session: AsyncSession, client_id: int, reports: List[Dict[str, Any]]):
    """
    Registers reports for a client in the database.
    Updates existing reports if matching (client_id, report_key).
    """
    print(f"📄 [ReportRegistry] Syncing {len(reports)} reports for client_id={client_id} to DB...")
    
    for report_data in reports:
        report_key = report_data.get("id") # The JSON uses 'id' as the key string
        
        # Check if exists
        statement = select(ReportRegistry).where(
            ReportRegistry.client_id == client_id,
            ReportRegistry.report_key == report_key
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        
        if existing:
            # Update - FULL OVERWRITE (JSON Authority)
            existing.display_name = report_data.get("display_name")
            existing.user_phrases = report_data.get("keywords", [])
            existing.sql_template = report_data.get("sql_template")
            existing.output_format = report_data.get("export_formats", ["xlsx"])[0] if report_data.get("export_formats") else "xlsx"
            
            # Optional fields - must be nullable/cleared if missing
            existing.date_column = report_data.get("date_column") # Set to None if missing
            
            existing.updated_at = datetime.utcnow()
            
            session.add(existing)
        else:
            # Create
            new_report = ReportRegistry(
                client_id=client_id,
                report_key=report_key,
                display_name=report_data.get("display_name"),
                user_phrases=report_data.get("keywords", []),
                sql_template=report_data.get("sql_template"),
                output_format="xlsx",
                date_column=report_data.get("date_column")
            )
            session.add(new_report)
    
    await session.commit()
    print(f"✅ [ReportRegistry] Committed {len(reports)} reports to DB.")

async def match_report(session: AsyncSession, client_id: int, user_input: str) -> Optional[ReportRegistry]:
    """
    Matches user input against registered reports for a client.
    Uses Python-side matching for flexibility with the JSON array of phrases.
    """
    # optimization: Fetch all reports for this client (usually small number < 50)
    # If scaling to thousands, would use PGVector or SQL ILIKE on a normalized tag table.
    
    statement = select(ReportRegistry).where(ReportRegistry.client_id == client_id)
    result = await session.execute(statement)
    reports = result.scalars().all()
    
    user_input_lower = user_input.lower().strip()
    
    for report in reports:
        # Check display name
        if report.display_name.lower() in user_input_lower:
            return report
            
        # Check phrases/keywords
        for phrase in report.user_phrases:
            if phrase.lower() in user_input_lower:
                return report
                
    return None

async def get_report_by_key(session: AsyncSession, client_id: int, report_key: str) -> Optional[ReportRegistry]:
    statement = select(ReportRegistry).where(
        ReportRegistry.client_id == client_id,
        ReportRegistry.report_key == report_key
    )
    result = await session.execute(statement)
    return result.scalars().first()
