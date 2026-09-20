import pymysql

conn = pymysql.connect(
    host='srv1556.hstgr.io', 
    user='u161593822_newlook', 
    password='1Q2w3e4r@#123', 
    db='u161593822_newlook', 
    port=3306,
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("""
        SELECT table_name, column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'u161593822_newlook' 
          AND (column_name LIKE '%voucher%' OR column_name LIKE '%payment%')
    """)
    rows = cur.fetchall()
    print("Voucher/Payment columns found:")
    for r in rows:
        tbl = r.get('table_name') or r.get('TABLE_NAME')
        col = r.get('column_name') or r.get('COLUMN_NAME')
        print(f"  {tbl}.{col}")

conn.close()
