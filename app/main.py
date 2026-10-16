from fastapi import FastAPI
from app.database import client
from contextlib import asynccontextmanager
from app.utils.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.routes.cart import router as cart_router
from app.routes.orders import router as order_router
from app.redis import shared_redis
from app.database import order_collection



@asynccontextmanager
async def lifespan(app: FastAPI):
  # MongoDB check
  await client.admin.command("ping")
  print("✅ MongoDB connected")
  
  await shared_redis.ping()       # ← add karo
  print("✅ Redis connected")

  # Indexes
  await order_collection.create_index("order_id", unique=True)
  await order_collection.create_index("user_id")
  await order_collection.create_index([("user_id", 1), ("status", 1)])
  await order_collection.create_index([("user_id", 1), ("created_at", -1)])
  print("✅ Indexes created")

  yield

  client.close()
  print("🔴 MongoDB disconnected")


app = FastAPI(
  title="Order APIs",
  description="Order service for NeuralCart",
  version="1.0.0",
  docs_url="/order-apis",
  lifespan=lifespan
)

# limiter configure kiya
app.state.limiter = limiter
app.add_exception_handler(
  RateLimitExceeded,
  _rate_limit_exceeded_handler
)

# Add Routes Here
app.include_router(cart_router)
app.include_router(order_router)



# Default Route
@app.get("/health")
async def health():
  return {"message": "Order Service Running"}