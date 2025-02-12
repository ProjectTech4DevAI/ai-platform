import asyncpg
import asyncio

async def test_connection():
    try:
        conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_first")
        print("✅ Successfully connected to PostgreSQL")
        await conn.close()
    except Exception as e:
        print("❌ Failed to connect:", e)

asyncio.run(test_connection())
