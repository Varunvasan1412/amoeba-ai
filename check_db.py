from sqlalchemy import create_engine, text
from app.core.config import settings

def check_db():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("\n--- CLIENTS ---")
        result = conn.execute(text('SELECT id, client_name FROM clientconfig'))
        for row in result:
            print(row)
            
        print("\n--- NAV ITEMS ---")
        result = conn.execute(text('SELECT id, label, module, path, client_id FROM navigationitem'))
        for row in result:
            print(row)

if __name__ == "__main__":
    check_db()
