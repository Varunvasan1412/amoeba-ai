from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pandas as pd
import os
from datetime import datetime
import json

# --- REPORTING TOOLS ---

def calculate_sales(year: int) -> str:
    """
    Simulated tool to calculate sales for a given year.
    In a real scenario, this would query the DB.
    """
    # Mock Logic
    import random
    total = random.randint(50000, 150000)
    return f"Total sales for {year}: ${total:,}"

def generate_pdf_report(data: str, filename: str = "report.pdf", filename_override: str = None) -> str:
    """
    Generates a PDF file with the given text data.
    Returns the file path.
    """
    if filename_override:
        filename = filename_override
    try:
        # Ensure 'public' dir exists for static serving if needed, or just temp
        output_dir = "static/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        c.drawString(100, 750, f"Amoeba AI Report - {datetime.now().strftime('%Y-%m-%d')}")
        c.drawString(100, 730, "------------------------------------------------")
        
        y = 700
        for line in data.split('\n'):
            c.drawString(100, y, line)
            y -= 20
            
        c.save()
        return filepath
    except Exception as e:
        return f"Error generating PDF: {e}"

def generate_excel_report(data_list: list, filename_override: str = None) -> str:
    """
    Generates an Excel file from a list of dictionaries.
    LEGACY: Use `export_sql_to_excel` for database dumps to avoid data exposure.
    """
    try:
        output_dir = "static/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        if filename_override:
             filename = filename_override
        else:
             filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
             
        filepath = os.path.join(output_dir, filename)
        
        df = pd.DataFrame(data_list)
        df.to_excel(filepath, index=False)
        
        return filepath
    except Exception as e:
        return f"Error generating Excel: {e}"

from sqlalchemy import create_engine
from app.core.context import current_db_url

def export_sql_to_excel(query: str, filename_override: str = None) -> str:
    """
    Executes a SQL query and streams the result directly to Excel.
    DATA BLIND MODE: The result data never passes through the LLM.
    """
    try:
        db_url = current_db_url.get()
        if not db_url:
            return "Error: No database connection available."
            
        # 🔧 FIX: Ensure Sync Driver for Pandas
        # Pandas requires a synchronous driver (e.g. pymysql vs aiomysql)
        if "mysql+aiomysql" in db_url:
            db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")
        elif "postgresql+asyncpg" in db_url:
            # Fallback for Postgres (requires psycopg2-binary installed)
            db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
            
        # Create Sync Engine for Pandas
        # (Pandas requires a sync connection or ADBC, keeping it simple here)
        engine = create_engine(db_url)
        
        output_dir = "static/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        if filename_override:
             filename = filename_override
             if not filename.endswith(".xlsx"): filename += ".xlsx"
        else:
             filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
             
        filepath = os.path.join(output_dir, filename)
        
        # Read & Write
        with engine.connect() as conn:
            # Chunking could be added here for massive tables, but for now strict read
            df = pd.read_sql(query, conn)
            df.to_excel(filepath, index=False)
            
        return filepath
        
    except Exception as e:
        return f"Error exporting to Excel: {e}"


def display_data_table(title: str, data_json: str) -> str:
    """
    Helper function to validate data for the display table tool.
    Returns success message or error.
    """
    try:
        if isinstance(data_json, str):
            data = json.loads(data_json)
        else:
            data = data_json
            
        if not isinstance(data, list):
            return "Error: Data must be a list of dictionaries."
            
        return f"Table '{title}' with {len(data)} rows ready for display."
    except Exception as e:
        return f"Error processing table data: {e}"

def export_query_result(query_payload: dict, format: str, db_url: str = None) -> str:
    """
    Rebuilds and executes a query using synchronous SQLAlchemy to generate an export file.
    Respects a maximum of 50,000 rows to prevent memory exhaustion.
    """
    from sqlalchemy import create_engine, MetaData, select as sa_select
    try:
        if not db_url:
            db_url = current_db_url.get()
        if not db_url:
            return "Error: No database connection available."
            
        table_name = query_payload.get("table_name")
        
        if not table_name:
            return "Error: Missing table_name in query payload."
        
        # Fix async driver strings for sync usage
        if "mysql+aiomysql" in db_url:
            db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")
        elif "postgresql+asyncpg" in db_url:
            db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
            
        engine = create_engine(db_url)
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        # Find table (fuzzy match)
        table = None
        norm_name = table_name.lower().strip().replace(" ", "_").replace("-", "_")
        for t_name, t_obj in metadata.tables.items():
            if t_name == table_name or t_name.lower().replace(" ", "_").replace("-", "_") == norm_name:
                table = t_obj
                break
        
        if table is None:
            return f"Error: Table '{table_name}' not found in database."
        
        max_rows = 50000
        stmt = sa_select(table).limit(max_rows)
        
        with engine.connect() as conn:
            result = conn.execute(stmt)
            rows = result.fetchall()
            columns = list(result.keys())
        
        if not rows:
            return "No data available to export."
             
        df = pd.DataFrame(rows, columns=columns)
        
        output_dir = "static/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{table_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        
        if format.lower() == "csv":
             filepath = os.path.join(output_dir, f"{filename}.csv")
             df.to_csv(filepath, index=False)
             return filepath
        elif format.lower() in ("xlsx", "excel"):
             filepath = os.path.join(output_dir, f"{filename}.xlsx")
             df.to_excel(filepath, index=False)
             return filepath
        elif format.lower() == "pdf":
             filepath = os.path.join(output_dir, f"{filename}.pdf")
             c = canvas.Canvas(filepath, pagesize=letter)
             c.drawString(50, 750, f"Amoeba AI Report - {table_name}")
             c.drawString(50, 730, "-" * 80)
             y = 700
             header_str = " | ".join([str(k)[:15] for k in df.columns])
             c.drawString(50, y, header_str)
             y -= 20
             for _, row in df.head(30).iterrows():
                 row_str = " | ".join([str(v)[:15] for v in row.values])
                 c.drawString(50, y, row_str)
                 y -= 15
                 if y < 50:
                     c.showPage()
                     y = 750
             if len(df) > 30:
                 c.drawString(50, y - 20, f"... and {len(df) - 30} more rows. Use Excel/CSV for full data.")
             c.save()
             return filepath
        else:
             return "Error: Unsupported file format."
             
    except Exception as e:
        return f"Error building export: {e}"

