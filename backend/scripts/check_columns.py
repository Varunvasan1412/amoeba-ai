import asyncio
import aiomysql

async def main():
    conn = await aiomysql.connect(
        host='srv1556.hstgr.io', 
        user='u161593822_newlook', 
        password='1Q2w3e4r@#123', 
        db='u161593822_newlook', 
        port=3306
    )
    async with conn.cursor() as cur:
        await cur.execute("SHOW COLUMNS FROM enquiry_header")
        res = await cur.fetchall()
        print([r[0] for r in res])
    conn.close()

asyncio.run(main())
