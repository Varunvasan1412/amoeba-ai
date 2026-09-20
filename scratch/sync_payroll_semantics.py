import requests
import json

API_KEY = "am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA"
BASE_URL = "https://amoeba.space"

# 1. Routes to register/learn
routes = [
    {
        "label": "Payroll Report",
        "path": "/payroll/report",
        "keywords": ["payroll", "report", "employee", "payroll report", "salary", "advance"]
    },
    {
        "label": "Payroll Employee Wise Report",
        "path": "/payroll/report",
        "keywords": ["payroll", "report", "employee", "employee wise report", "wise report"]
    },
    {
        "label": "Payroll List",
        "path": "/payroll/list",
        "keywords": ["payroll", "list", "attendance", "daily attendance", "attendance logs"]
    },
    {
        "label": "Payroll History",
        "path": "/payroll/list",
        "keywords": ["payroll", "history", "payroll history", "attendance details", "logs"]
    }
]

r_route = requests.post(f"{BASE_URL}/api/routes/learn?api_key={API_KEY}", json=routes, timeout=60)
print("Route Learn Status:", r_route.status_code, r_route.text)


# 2. Semantic Mappings for Payroll
payroll_report_query = (
    "SELECT e.number AS `Employee Code`, e.name AS `Employee Name`, "
    "COALESCE(et.name, '') AS `Designation`, e.salary AS `Salary`, "
    "e.ot_amount AS `OT Amount`, e.salary_advance AS `Advance` "
    "FROM employee e "
    "LEFT JOIN employee_type et ON et.id = e.employee_type_id "
    "WHERE e.status = 1 "
    "ORDER BY e.id ASC"
)

attendance_query = (
    "SELECT DATE_FORMAT(ah.attendance_date, '%d/%m/%Y') AS `Attendance Date`, "
    "COUNT(al.al_id) AS `Total Employees`, "
    "COALESCE(SUM(al.al_present), 0) AS `Present`, "
    "COALESCE(SUM(al.al_absent), 0) AS `Absent` "
    "FROM attendance_header ah "
    "LEFT JOIN attendance_logs al ON al.header_id = ah.id "
    "GROUP BY ah.id, ah.attendance_date "
    "ORDER BY ah.attendance_date DESC"
)

semantics = []

# Distinct Payroll Report mappings (employee table, 13 records)
for lbl in [
    "Payroll Report", 
    "Payroll Employee Wise Report", 
    "Employee Wise Report", 
    "Employee Payroll Report", 
    "Payroll Summary Report"
]:
    semantics.append({
        "ui_label": lbl,
        "database_table": "employee",
        "source_file": "application/controllers/Payroll.php::report -> application/views/payroll/report.php",
        "ui_columns": "Employee Code, Employee Name, Designation, Salary, OT Amount, Advance [Filter: e.status = 1]",
        "default_filter": "e.status = 1",
        "base_query": payroll_report_query,
        "required_joins": "LEFT JOIN employee_type et ON et.id = e.employee_type_id",
        "tab_group": "Payroll"
    })

# Distinct Payroll History / Attendance mappings (attendance_header table, 4 records)
for lbl in [
    "Payroll History Details", 
    "Payroll History List", 
    "Payroll History", 
    "Daily Attendance Logs", 
    "Attendance Logs", 
    "Payroll List",
    "Attendance List"
]:
    semantics.append({
        "ui_label": lbl,
        "database_table": "attendance_header",
        "source_file": "application/controllers/Payroll.php::list -> application/views/payroll/list.php",
        "ui_columns": "Date, Total Present, Total Absent, Total Half Day, Total Late",
        "default_filter": None,
        "base_query": attendance_query,
        "required_joins": None,
        "tab_group": "Payroll"
    })

r_sem = requests.post(f"{BASE_URL}/api/semantic/sync?api_key={API_KEY}", json=semantics, timeout=60)
print("Semantic Sync Status:", r_sem.status_code, r_sem.text)

