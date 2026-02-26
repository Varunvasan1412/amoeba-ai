from contextvars import ContextVar

# Usage: current_db_url.set("postgresql://...")
current_db_url: ContextVar[str] = ContextVar("current_db_url", default=None)
