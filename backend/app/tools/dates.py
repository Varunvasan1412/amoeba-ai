
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

    # 0. Specific Month Names (e.g., "March", "March 2026", "in June")
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    # Short names
    short_months = [m[:3] for m in months]
    
    month_pattern = r'\b(' + '|'.join(months + short_months) + r')\b'
    month_match = re.search(month_pattern, query)
    
    if month_match:
        month_str = month_match.group(1)
        # Find index (1-based)
        try:
            m_idx = months.index(month_str) + 1
        except ValueError:
            m_idx = short_months.index(month_str) + 1
            
        # Check for year
        year_match = re.search(r'\b(20\d{2})\b', query)
        year = int(year_match.group(1)) if year_match else today.year
        
        start_date = datetime(year, m_idx, 1)
        if m_idx == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, m_idx + 1, 1) - timedelta(days=1)
            
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 1. "Between DATE and DATE" or "From DATE to DATE"
    between_match = re.search(r'(?:between|from)\s+(.+?)\s+(?:and|to)\s+(.+?)(?:\s|$)', query)
    if between_match:
        raw_start, raw_end = between_match.group(1).strip(), between_match.group(2).strip()
        parsed_start = _parse_flexible_date(raw_start)
        parsed_end = _parse_flexible_date(raw_end)
        if parsed_start and parsed_end:
            return parsed_start.strftime("%Y-%m-%d"), parsed_end.strftime("%Y-%m-%d")

    # 2. Year handling (e.g. "2023", "in 2022")
    year_match = re.search(r'\b(20\d{2})\b', query)
    if year_match and not re.search(r'last\s+\d+\s+days', query):
        year = int(year_match.group(1))
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 3. "This Year"
    if "this year" in query:
        start_date = datetime(today.year, 1, 1)
        end_date = datetime(today.year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 4. "Last Year"
    if "last year" in query:
        year = today.year - 1
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 5. "This Month"
    if "this month" in query:
        start_date = datetime(today.year, today.month, 1)
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 6. "Last Month"
    if "last month" in query:
        last_day_last_month = datetime(today.year, today.month, 1) - timedelta(days=1)
        start_date = datetime(last_day_last_month.year, last_day_last_month.month, 1)
        end_date = last_day_last_month
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 7. "This Week"
    if "this week" in query:
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 8. "Last Week"
    if "last week" in query:
        start_date = today - timedelta(days=today.weekday() + 7)
        end_date = start_date + timedelta(days=6)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 9. "Last X Days"
    days_match = re.search(r'last\s+(\d+)\s+days', query)
    if days_match:
        days = int(days_match.group(1))
        end_date = today
        start_date = today - timedelta(days=days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 10. "Yesterday"
    if "yesterday" in query:
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")

    # 11. "Today"
    if "today" in query:
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    # 12. Single date: "on DD-MM-YYYY" or just a date like "20-03-2026"
    single_date_match = re.search(r'(?:on\s+)?(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4})', query)
    if single_date_match:
        parsed = _parse_flexible_date(single_date_match.group(1))
        if parsed:
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%Y-%m-%d")

    return None, None


def parse_date_range(query: str) -> dict:
    """
    Wrapper that returns a structured dict for semantic use.
    Returns: {"start_date": str|None, "end_date": str|None, "matched": bool}
    """
    start, end = normalize_date_range(query)
    return {
        "start_date": start,
        "end_date": end,
        "matched": start is not None
    }


def _parse_flexible_date(raw: str):
    """
    Attempts to parse a date string in multiple formats.
    Supports: DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD
    """
    formats = [
        "%d-%m-%Y", "%Y-%m-%d",
        "%d/%m/%Y", "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    raw = raw.strip().rstrip(".,;:!? ")
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def strip_date_phrases(query: str) -> str:
    """
    Removes detected date phrases from a query string.
    Useful for entity resolution where date markers would cause a mismatch.
    """
    query = query.lower()
    
    # 1. Between/From patterns
    query = re.sub(r'\b(?:between|from)\s+.+?\s+(?:and|to)\s+.+?(\s|$)', ' ', query)
    
    # 2. Last X days/records
    query = re.sub(r'\blast\s+\d+\s+(?:days|records|items|rows|entries)\b', ' ', query)
    query = re.sub(r'\bshow\s+\d+\s+(?:records|items|rows|entries)\b', ' ', query)
    
    # 3. Fixed phrases and Months
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    short_months = [m[:3] for m in months]
    
    phrases = [
        "this year", "last year", "this month", "last month", 
        "this week", "last week", "yesterday", "today", "latest", "recent", "month"
    ] + months + short_months
    for p in phrases:
        query = re.sub(rf'\b{p}\b', ' ', query)
        
    # 4. Years (2000-2099)
    query = re.sub(r'\b20\d{2}\b', ' ', query)
    
    # 5. Single dates: "on DD-MM-YYYY" or standalone "20-03-2026"
    query = re.sub(r'\bon\s+\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b', ' ', query)
    query = re.sub(r'\b\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b', ' ', query)
    
    # 6. Prepositions and filler phrases often around dates
    filler_phrases = [
        r"which\s+are\s+created\s+on",
        r"that\s+are\s+created\s+on",
        r"which\s+were\s+created\s+on",
        r"that\s+were\s+created\s+on",
        r"which\s+are\s+created\s+at",
        r"that\s+are\s+created\s+at",
        r"which\s+were\s+created\s+at",
        r"that\s+were\s+created\s+at",
        r"created\s+on",
        r"created\s+at",
        r"made\s+on",
        r"made\s+at",
        r"which\s+are",
        r"that\s+are",
        r"records\s+of",
        r"items\s+of"
    ]
    for fp in filler_phrases:
        query = re.sub(rf'\b{fp}\b', ' ', query)

    # 7. Common prepositions/noise
    noise = ["from", "during", "done", "was", "were", "on", "in", "at", "for", "of", "created"]
    for n in noise:
        query = re.sub(rf'\b{n}\b', ' ', query)
    
    # 8. Clean up extra whitespace
    query = re.sub(r'\s+', ' ', query).strip()
    return query
