# setup.py
import asyncio
import os
from dotenv import load_dotenv
from src.tools.supabase_tool import SupabaseTool

async def setup_database():
    """Run this to set up your database tables"""
    
    load_dotenv()
    
    # Read SQL schema
    with open("database/schema.sql", "r") as f:
        schema = f.read()
    
    # Initialize tool
    tool = SupabaseTool()
    await tool.init_pool()
    
    # Execute schema
    async with tool.pool.acquire() as conn:
        try:
            await conn.execute(schema)
            print("✅ Database schema created successfully!")
        except Exception as e:
            print(f"❌ Error creating schema: {e}")
    
    await tool.close_pool()

if __name__ == "__main__":
    asyncio.run(setup_database())