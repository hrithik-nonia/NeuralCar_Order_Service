from dotenv import load_dotenv
import os
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# mongodb client create kiya
client = AsyncIOMotorClient(os.getenv("MONGO_URI"),
                            maxPoolSize=50,   # connection pool added
                            minPoolSize=10,
                            maxIdleTimeMS=60000,
                            serverSelectionTimeoutMS=5000
                            )

# DB create
db = client[os.getenv("DATABASE_NAME")]


# Collection Create
order_collection = db["order"]
cart_collection = db["cart"]