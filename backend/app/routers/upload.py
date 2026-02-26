from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
import uuid

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Uploads a file (PDF, Excel, CSV) to the server.
    Returns the file_path which the AI can then read using `tool_read_file`.
    """
    try:
        # Generate unique filename to avoid collisions
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "filename": file.filename,
            "filepath": file_path,
            "message": "File uploaded successfully. Pass 'filepath' to the AI."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
