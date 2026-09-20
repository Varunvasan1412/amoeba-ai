import pymysql

conn = pymysql.connect(
    host="srv1556.hstgr.io",
    user="u161593822_newlook",
    password="1Q2w3e4r@#123",
    database="u161593822_newlook",
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("SELECT * FROM attendance_header")
    for r in cur.fetchall():
        print("Header:", r)
        
    cur.execute("SHOW TABLES LIKE '%attendance%'")
    for t in cur.fetchall():
        print("Table:", t)

conn.close()
