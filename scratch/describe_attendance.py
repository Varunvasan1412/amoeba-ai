import pymysql

conn = pymysql.connect(
    host="srv1556.hstgr.io",
    user="u161593822_newlook",
    password="1Q2w3e4r@#123",
    database="u161593822_newlook",
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("DESCRIBE attendance_header")
    for col in cur.fetchall():
        print(f"{col['Field']}: {col['Type']}")

conn.close()
