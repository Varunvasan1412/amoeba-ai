import os
import zipfile

def zip_project(source_dir, output_filename):
    # Folders to exclude
    EXCLUDE_DIRS = {
        'node_modules', 
        'venv', 
        '.venv', 
        '__pycache__', 
        '.git', 
        'dist', 
        'postgres_data',
        'site-packages' # Just in case
    }
    
    EXCLUDE_FILES = {
        'dummy_erp.db',
        '.DS_Store',
        'frontend.zip' # Explicitly exclude known issue
    }

    print(f"📦 Packing project from: {source_dir}")
    print(f"🚫 Excluding: {EXCLUDE_DIRS}")
    
    zip_path = os.path.join(source_dir, output_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                    
                if file == output_filename:
                    continue
                    
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                
                print(f"  + Adding: {arcname}")
                zipf.write(file_path, arcname)
                
    print(f"\n✅ Project successfully packed to: {zip_path}")

if __name__ == "__main__":
    # Run from root
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUTPUT_FILE = "amoeba-ai-dist.zip"
    zip_project(ROOT_DIR, OUTPUT_FILE)
