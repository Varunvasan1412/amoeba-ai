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
    print("--- expence_details count and sample ---")
    cur.execute("SELECT count(*) as cnt FROM expence_details")
    print("Count:", cur.fetchone()['cnt'])
    cur.execute("SELECT * FROM expence_details LIMIT 3")
    for r in cur.fetchall():
        print(r)

    print("\n--- ledger count and sample ---")
    cur.execute("SELECT count(*) as cnt FROM ledger")
    print("Count:", cur.fetchone()['cnt'])
    cur.execute("SELECT * FROM ledger LIMIT 3")
    for r in cur.fetchall():
        print(r)

conn.close()
