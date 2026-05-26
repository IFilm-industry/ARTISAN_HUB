import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

client = None
db = None

async def connect_db():
    global client, db
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/artisan_hub")
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[i] MongoDB connection attempt {attempt}/{max_retries}...")
            client = AsyncIOMotorClient(
                mongo_uri, 
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000
            )
            # Verify the connection by pinging
            await client.admin.command('ping')
            
            # Parse db name from URI
            db_name = "artisan_hub"
            # Get everything after the last '/' and before '?'
            if "/" in mongo_uri:
                last_part = mongo_uri.split("/")[-1]
                if "?" in last_part:
                    last_part = last_part.split("?")[0]
                if last_part:
                    db_name = last_part
            
            db = client[db_name]
            print(f"[OK] MongoDB Connected: {db_name}")
            return
        except Exception as e:
            print(f"[ERR] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                print("[i] Waiting 5 seconds before retry...")
                await asyncio.sleep(5)
    
    print("\n[WARN] Could not connect to MongoDB after 5 attempts.")
    print("   The server is running but database features won't work.")
    print("   Check your MONGO_URI, Atlas Network Access, and credentials.\n")

def get_db():
    return db
