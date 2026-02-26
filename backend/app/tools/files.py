import pandas as pd
import os

async def read_file_content(file_path: str):
    """
    Reads a file (Excel, CSV) and returns a summary/markdown representation.
    Used by the AI to understand uploaded data.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    
    try:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".csv":
            df = pd.read_csv(file_path)
            return df.to_markdown(index=False)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
            return df.to_markdown(index=False)
        elif ext == ".pdf":
            # For PDF, we might need a library like PyPDF2, but for now let's handle tabular data
            # or return a placeholder if pdf lib not installed.
            # Assuming tabular data focus for now based on 'Excel' request.
            return "PDF reading not fully implemented. Upload .csv or .xlsx for analysis."
        else:
            return "Error: Unsupported file format."
            
    except Exception as e:
        return f"Error reading file: {str(e)}"
