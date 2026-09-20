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
    q = (
        "SELECT "
        "e.number AS `Employee Code`, "
        "e.name AS `Employee Name`, "
        "COALESCE(et.name, '') AS `Designation`, "
        "e.salary AS `Salary`, "
        "e.ot_amount AS `OT Amount`, "
        "e.salary_advance AS `Advance` "
        "FROM employee e "
        "LEFT JOIN employee_type et ON et.id = e.employee_type_id "
        "WHERE e.status = 1 "
        "ORDER BY e.id ASC"
    )
    cur.execute(q)
    rows = cur.fetchall()
    print(f"Total rows returned: {len(rows)}")
    for r in rows:
        print(" ", r)

conn.close()
