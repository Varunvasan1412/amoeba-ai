from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, inspect, text
from app.models.client_config import ClientConfig

class RecordSelectorService:
    @staticmethod
    async def get_records_for_selection(client_id: int, table_name: str, session: AsyncSession) -> List[Dict[str, Any]]:
        if not table_name or " " in table_name:
            raise ValueError(f"Invalid table name passed to selector: {table_name}")
        
        """
        Fetches records with high-quality, human-readable labels.
        Concatenates multiple columns for better context.
        """
        client_config = await session.get(ClientConfig, client_id)
        if not client_config:
            return []

        engine = create_engine(client_config.db_connection_url)
        inspector = inspect(engine)
        pk_col = inspector.get_pk_constraint(table_name)["constrained_columns"][0] or "id"
        cols = [c["name"] for c in inspector.get_columns(table_name)]
        
        # Identify interesting columns to combine
        # Priority: Person > Name > Code/Number > Designation > Status
        candidates = ["person", "name", "full_name", "number", "no", "code", "designation", "status"]
        selected_cols = []
        for cand in candidates:
            # Match exact or partial
            match = next((c for c in cols if c.lower() == cand or c.lower().endswith(f"_{cand}")), None)
            if match and match not in selected_cols:
                selected_cols.append(match)
            if len(selected_cols) >= 3: break # Don't over-clutter

        # If none found, fallback to ID
        if not selected_cols: selected_cols = [pk_col]

        query_cols = f"{pk_col}, " + ", ".join(selected_cols)
        
        # Try to join parent if possible
        parent_alias = ""
        join_sql = ""
        for fk in inspector.get_foreign_keys(table_name):
            if fk["referred_table"] in ["customer", "enquiry_header"]:
                parent_cols = [c["name"] for c in inspector.get_columns(fk["referred_table"])]
                p_name = next((c for c in parent_cols if "name" in c or "number" in c), None)
                if p_name:
                    query_cols += f", p.{p_name} AS parent_ctx"
                    join_sql = f"LEFT JOIN {fk['referred_table']} p ON t.{fk['constrained_columns'][0]} = p.id"
                    break

        try:
            sql = f"SELECT {query_cols} FROM {table_name} t {join_sql} ORDER BY t.{pk_col} DESC LIMIT 100"
            with engine.connect() as conn:
                res = conn.execute(text(sql))
                records = []
                for row in res:
                    rid = row[0]
                    # Row mapping: id is index 0, ctx columns are 1 to len(selected_cols)
                    # parent_ctx is last if it exists
                    ctx_vals = [str(v) for v in row[1:1+len(selected_cols)] if v and str(v).strip()]
                    parent_ctx = row[-1] if "parent_ctx" in sql else None
                    
                    label = " | ".join(ctx_vals) if ctx_vals else f"Entry #{rid}"
                    if parent_ctx:
                        label = f"{parent_ctx} » {label}"
                    
                    records.append({"id": rid, "label": label})
                return records
        except Exception as e:
            print(f"⚠️ Smart Selector Error: {e}")
            return [{"id": rid, "label": f"Record #{rid}"} for rid in range(1, 11)] # Last resort
