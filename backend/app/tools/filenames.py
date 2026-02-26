
import re
from datetime import datetime

def generate_deterministic_filename(report_name: str, start_date: str = None, end_date: str = None, extension: str = "pdf") -> str:
    """
    Generates a deterministic filename: {report_name}_{range}.{extension}
    Example: sales_summary_2023-01-01_to_2023-12-31.pdf
    """
    # 1. Clean Report Name (snake_case)
    clean_name = report_name.lower()
    clean_name = re.sub(r'[^a-z0-9]+', '_', clean_name).strip('_')
    
    # 2. Add Date components
    date_part = ""
    if start_date and end_date:
        if start_date == end_date:
            date_part = f"_{start_date}"
        else:
            date_part = f"_{start_date}_to_{end_date}"
    elif start_date:
         date_part = f"_{start_date}"
    else:
         # Fallback to today if no date range
         today = datetime.now().strftime("%Y-%m-%d")
         date_part = f"_{today}"

    # 3. Assemble
    filename = f"{clean_name}{date_part}.{extension.strip('.')}"
    return filename
