import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import asyncio
import os

sys.path.insert(0, os.path.abspath("backend"))

from app.core.database import async_session
from app.services.intent_service import resolve_crud_intent

async def main():
    async with async_session() as session:
        res = await resolve_crud_intent("List invoices", 4, session)
        print("RESULT FOR 'List invoices':", res)

if __name__ == "__main__":
    asyncio.run(main())
