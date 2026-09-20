import psycopg2

CONN_PARAMS = [
    {"host": "localhost", "port": 5432, "dbname": "amoeba", "user": "user", "password": "password"},
]

for params in CONN_PARAMS:
    try:
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        
        print("=" * 80)
        print("SEMANTIC MAPPINGS for 'parts setting' (client_id=4)")
        print("=" * 80)
        cur.execute("""
            SELECT id, ui_label, database_table, ui_columns, base_query, default_filter
            FROM semantic_mapping 
            WHERE client_id = 4 
            AND (
                LOWER(ui_label) LIKE '%parts setting%' 
                OR LOWER(ui_label) LIKE '%parts%'
                OR LOWER(database_table) LIKE '%part%'
            )
            ORDER BY ui_label
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"  ID={r[0]} | Label='{r[1]}' | Table='{r[2]}' | UICols='{r[3]}' | BaseQuery={r[4][:80] if r[4] else 'None'} | Filter={r[5]}")
        if not rows:
            print("  (no results)")
            
        cur.close()
        conn.close()
        break
    except Exception as e:
        print(f"Failed: {e}")
