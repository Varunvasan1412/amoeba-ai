from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.field_metadata import FieldMetadata
from app.models.client_config import ClientConfig
from typing import List, Dict, Any, Optional

def _detect_storage_type(sa_type: str) -> str:
    """Maps SQLAlchemy types to Amoeba internal storage types."""
    t = sa_type.upper()
    if "INT" in t: return "integer"
    if "DECIMAL" in t or "FLOAT" in t or "NUMERIC" in t: return "float"
    if "BOOL" in t: return "boolean"
    if "DATE" in t or "TIME" in t or "TIMESTAMP" in t: return "date"
    return "string"

async def generate_field_metadata(client_id: int, session: AsyncSession):
    """
    Analyzes a client's database and populates field_metadata with smart defaults.
    """
    stmt = select(ClientConfig).where(ClientConfig.id == client_id)
    result = await session.execute(stmt)
    client = result.scalars().first()
    if not client:
        return 0
        
    try:
        # We use a sync engine for discovery
        sync_url = client.db_connection_url
        if sync_url.startswith("postgresql+asyncpg://"): sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        elif sync_url.startswith("postgresql://"): sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
        elif sync_url.startswith("mysql+aiomysql://"): sync_url = sync_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        elif sync_url.startswith("mysql://"): sync_url = sync_url.replace("mysql://", "mysql+pymysql://")
        elif sync_url.startswith("sqlite+aiosqlite://"): sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
        engine = create_engine(sync_url)
        inspector = inspect(engine)
    except Exception as e:
        print(f"❌ Metadata Discovery Error: {e}")
        return 0
        
    # Get existing metadata to avoid duplicates
    stmt_existing = select(FieldMetadata).where(FieldMetadata.client_id == client_id)
    result_existing = await session.execute(stmt_existing)
    existing_meta = result_existing.scalars().all()
    # Map of (table, column) -> object
    existing_map = {(m.table_name, m.column_name): m for m in existing_meta}
    
    new_metadata = []
    
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        
        has_primary_date = any(m.is_primary_date for m in existing_meta if m.table_name == table_name)
        
        for col in columns:
            col_name = col["name"]
            if (table_name, col_name) in existing_map:
                continue
                
            # Smart Logic for Defaults
            label = col_name.replace("_", " ").title()
            input_type = "text"
            storage_type = _detect_storage_type(str(col["type"]))
            
            # 1. Detect Read-Only (Primary Keys)
            readonly = col_name in pk_cols
            
            # 2. Detect Checkboxes
            if storage_type == "boolean" or col_name.startswith("is_") or col_name.startswith("has_"):
                input_type = "checkbox"
                
            # 3. Detect Textareas
            if storage_type == "string" and (col.get("type").__class__.__name__ == "TEXT" or "desc" in col_name.lower()):
                input_type = "textarea"
                
            # 4. Detect Dates
            is_primary_date = False
            if storage_type == "date":
                input_type = "date"
                # Heuristic for primary date
                if not has_primary_date:
                    if col_name.lower() in ["created_at", "date", "entry_date", "createddate"]:
                        is_primary_date = True
                        has_primary_date = True
            
            # 5. Detect Dropdowns (Heuristic: ends with _id)
            if col_name.endswith("_id") and not readonly:
                input_type = "dropdown"
            
            new_meta = FieldMetadata(
                client_id=client_id,
                table_name=table_name,
                column_name=col_name,
                label=label,
                input_type=input_type,
                storage_type=storage_type,
                required=not col.get("nullable", True),
                readonly=readonly,
                is_visible=True,
                is_primary_date=is_primary_date,
                default_value=str(col.get("default")) if col.get("default") is not None else None
            )
            new_metadata.append(new_meta)
        
        # If no primary date was found via heuristics, pick the first date column
        if not has_primary_date:
            for meta in new_metadata:
                if meta.table_name == table_name and meta.storage_type == "date":
                    meta.is_primary_date = True
                    break
            
    if new_metadata:
        session.add_all(new_metadata)
        await session.commit()
        
    return len(new_metadata)

async def get_field_options(client_id: int, meta: FieldMetadata, session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Fetches dropdown options from the client's database with smart heuristic discovery.
    """
    stmt = select(ClientConfig).where(ClientConfig.id == client_id)
    result = await session.execute(stmt)
    client = result.scalars().first()
    if not client or not client.db_connection_url:
        return []
        
    try:
        sync_url = client.db_connection_url
        if sync_url.startswith("postgresql+asyncpg://"): sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        elif sync_url.startswith("postgresql://"): sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
        elif sync_url.startswith("mysql+aiomysql://"): sync_url = sync_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        elif sync_url.startswith("mysql://"): sync_url = sync_url.replace("mysql://", "mysql+pymysql://")
        elif sync_url.startswith("sqlite+aiosqlite://"): sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
        engine = create_engine(sync_url)
        inspector = inspect(engine)

        source_table = meta.data_source_table
        val_col = meta.value_column or "id"
        disp_col = meta.display_column

        # Auto-discover source table and columns if not explicitly configured
        if not source_table or not disp_col:
            col_raw = (meta.column_name or "").lower().strip()
            # Strip common foreign key patterns: city_id -> city, business_city_id -> city
            stem = col_raw[:-3] if col_raw.endswith("_id") else col_raw
            candidates = [stem]
            if "_" in stem:
                candidates.append(stem.split("_")[-1]) # e.g. business_city -> city, customer_category -> category
                candidates.append(stem.replace("business_", "").replace("customer_", ""))
            
            # Common plurals and prefixes
            extended_candidates = []
            for c in candidates:
                extended_candidates.extend([c, f"mst_{c}", f"tbl_{c}", f"{c}s", f"{c}es", f"{c}_master"])
            
            all_tables = inspector.get_table_names()
            table_match_map = {t.lower(): t for t in all_tables}

            found_table = None
            if source_table and source_table.lower() in table_match_map:
                found_table = table_match_map[source_table.lower()]
            else:
                for cand in extended_candidates:
                    if cand.lower() in table_match_map:
                        found_table = table_match_map[cand.lower()]
                        break
            
            if not found_table:
                return []
            
            source_table = found_table
            cols = [c["name"] for c in inspector.get_columns(source_table)]
            cols_lower = {c.lower(): c for c in cols}

            # Find value column (primary key or 'id')
            if not val_col or val_col.lower() not in cols_lower:
                pk_cols = inspector.get_pk_constraint(source_table).get("constrained_columns", [])
                if pk_cols:
                    val_col = pk_cols[0]
                elif "id" in cols_lower:
                    val_col = cols_lower["id"]
                else:
                    val_col = cols[0]
            else:
                val_col = cols_lower[val_col.lower()]

            # Find display column (name, title, label, description, code, etc.)
            if not disp_col or disp_col.lower() not in cols_lower:
                label_candidates = [
                    "name", "title", "label", "display_name", f"{stem}_name", 
                    "category_name", "group_name", "city_name", "description", "code"
                ]
                for lc in label_candidates:
                    if lc in cols_lower:
                        disp_col = cols_lower[lc]
                        break
                if not disp_col:
                    # Pick first non-id string column
                    for c in cols:
                        if c != val_col and "id" not in c.lower():
                            disp_col = c
                            break
                if not disp_col:
                    disp_col = val_col
            else:
                disp_col = cols_lower[disp_col.lower()]

        with engine.connect() as conn:
            # Check if log_status or is_active filter applies
            cols_in_src = {c["name"].lower() for c in inspector.get_columns(source_table)}
            where_clause = ""
            if "log_status" in cols_in_src:
                where_clause = "WHERE log_status = 1"
            elif "is_active" in cols_in_src:
                where_clause = "WHERE is_active = 1"
            elif "status" in cols_in_src:
                where_clause = "WHERE status = 'active' OR status = 1"

            query = text(f"SELECT DISTINCT {val_col} AS value, {disp_col} AS label FROM {source_table} {where_clause} ORDER BY {disp_col} ASC LIMIT 1000")
            rows = conn.execute(query).mappings().all()
            options = []
            for row in rows:
                v = row["value"]
                lbl = row["label"]
                if lbl is not None and str(lbl).strip() != "":
                    options.append({"value": v, "label": str(lbl).strip()})
            return options
    except Exception as e:
        print(f"[WARN] Failed to fetch options for {getattr(meta, 'table_name', '')}.{getattr(meta, 'column_name', '')}: {e}")
        return []
