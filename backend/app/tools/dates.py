
from datetime import datetime, timedelta
import re

def normalize_date_range(query: str):
    """
    Parses natural language date queries and returns a tuple (start_date, end_date) in YYYY-MM-DD format.
    Returns (None, None) if no date range is detected.
    """
    today = datetime.now()
    query = query.lower()
    
    start_date = None
    end_date = None

    # 1. Year handling (e.g. "2023", "in 2022")
    year_match = re.search(r'\b(20\d{2})\b', query)
    if year_match:
        year = int(year_match.group(1))
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 2. "This Year"
    if "this year" in query:
        start_date = datetime(today.year, 1, 1)
        end_date = datetime(today.year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 3. "Last Year"
    if "last year" in query:
        year = today.year - 1
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 4. "This Month"
    if "this month" in query:
        start_date = datetime(today.year, today.month, 1)
        # End date logic: 1st of next month - 1 day
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 5. "Last Month"
    if "last month" in query:
        # First day of this month - 1 day = Last day of last month
        last_day_last_month = datetime(today.year, today.month, 1) - timedelta(days=1)
        start_date = datetime(last_day_last_month.year, last_day_last_month.month, 1)
        end_date = last_day_last_month
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 6. "Last X Days" (New)
    days_match = re.search(r'last\s+(\d+)\s+days', query)
    if days_match:
        days = int(days_match.group(1))
        end_date = today
        start_date = today - timedelta(days=days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 7. "Today"
    if "today" in query:
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    return None, None
