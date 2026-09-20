import pymysql

conn = pymysql.connect(
    host="srv1556.hstgr.io",
    user="u161593822_newlook",
    password="1Q2w3e4r@#123",
    database="u161593822_newlook",
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    query = (
        "SELECT DATE_FORMAT(ah.attendance_date, '%d/%m/%Y') AS `Attendance Date`, "
        "COUNT(al.al_id) AS `Total Employees`, "
        "COALESCE(SUM(al.al_present), 0) AS `Present`, "
        "COALESCE(SUM(al.al_absent), 0) AS `Absent` "
        "FROM attendance_header ah "
        "LEFT JOIN attendance_logs al ON al.header_id = ah.id "
        "GROUP BY ah.id, ah.attendance_date "
        "ORDER BY ah.attendance_date DESC"
    )
    cur.execute(query)
    rows = cur.fetchall()
    print(f"Total Rows: {len(rows)}")
    for r in rows:
        print(r)

conn.close()
