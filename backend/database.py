"""
MongoDB database connection and helpers
"""
import motor.motor_asyncio
from datetime import datetime, timezone
from backend.config import settings


class Database:
    client: motor.motor_asyncio.AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        """Connect to MongoDB"""
        cls.client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
        cls.db = cls.client[settings.MONGODB_DB]
        
        # Create indexes
        await cls.db.api_keys.create_index("key_hash", unique=True)
        await cls.db.api_keys.create_index("is_active")
        await cls.db.usage_logs.create_index("timestamp")
        await cls.db.usage_logs.create_index("api_key_id")
        await cls.db.usage_logs.create_index([("api_key_id", 1), ("timestamp", -1)])
        await cls.db.conversations.create_index("api_key_id")
        await cls.db.conversations.create_index("updated_at")
        await cls.db.rate_limits.create_index("key", unique=True)
        await cls.db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
        
        print(f"[OK] Connected to MongoDB: {settings.MONGODB_DB}")

    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB"""
        if cls.client:
            cls.client.close()
            print("[INFO] Disconnected from MongoDB")

    @classmethod
    async def is_connected(cls) -> bool:
        """Check if MongoDB is connected"""
        try:
            if cls.client:
                await cls.client.admin.command("ping")
                return True
        except Exception:
            pass
        return False

    # ============ Collections ============
    
    @classmethod
    def api_keys(cls):
        return cls.db.api_keys

    @classmethod
    def usage_logs(cls):
        return cls.db.usage_logs

    @classmethod
    def conversations(cls):
        return cls.db.conversations

    @classmethod
    def messages(cls):
        return cls.db.messages

    @classmethod
    def rate_limits(cls):
        return cls.db.rate_limits


db = Database()
