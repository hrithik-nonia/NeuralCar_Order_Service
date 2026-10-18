from fastapi import APIRouter, Request, status, Depends, Query, HTTPException
from app.utils.limiter import limiter
from app.models.order import OrderCreateInput
from app.utils.dependency import get_current_user
from app.utils.product_client import get_product
from app.redis import shared_redis
from app.database import order_collection
from app.utils.helper_functions import generate_order_id
from datetime import datetime, timezone
import json
from app.utils.kafka_producer import publish_event

router = APIRouter(prefix="/Order", tags=["Order APIs"])

# Create Order
@router.post("/add/{product_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def add_order(
    request: Request,
    product_id: str,
    order_data: OrderCreateInput,
    user: dict = Depends(get_current_user)
) -> dict | None:

  # 1. Sirf user order kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user order kar sakta hai"
      )

  # 2. Product Service se product lo
  product = await get_product(product_id)

  # 3. Stock check
  if order_data.quantity > product.get("stock", 0):
      raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail=f"Sirf {product['stock']} units available hain"
      )

  # 4. Order banao
  order_id = generate_order_id()
  user_id = user.get("id")
  total_price = round(product["price"] * order_data.quantity, 2)

  order = {
      "order_id": order_id,
      "user_id": user_id,
      "product": {
          "product_id": product_id,
          "name": product["name"],
          "price": product["price"],
          "quantity": order_data.quantity,
          "total_price": total_price,
      },
      "shipping_address": order_data.shipping_address.model_dump(),
      "payment": {
          "method": order_data.payment.payment_method,
          "status": "pending",
      },
      "status": "pending",
      "created_at": datetime.now(timezone.utc).isoformat(),
  }

  # 5. DB mein save karo
  await order_collection.insert_one(order)
  
  # ← Yahan add karo
  await publish_event(
    "neuralmcart.order.placed",
    {
        "order_id": order_id,
        "user_id": user_id,
        "items": order["product"],
        "total": total_price
    }
  )
  
  # Redis ke liye _id hata do
  order_for_cache = {k: v for k, v in order.items() if k != "_id"}

  # 6. Redis mein cache karo — 7 days
  await shared_redis.setex(
      f"order:{order_id}",
      7 * 24 * 60 * 60,
      json.dumps(order_for_cache)
  )

  return {
      "message": "Order place ho gaya",
      "order_id": order_id,
      "total_price": total_price,
      "status": "pending"
  }
      
  
# Get Orders
@router.get("/all-orders", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def all_orders(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user dekh sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user order dekh sakta hai"
      )

  user_id = user.get("id")
  skip = (page - 1) * limit

  # 2. Cache key
  cache_key = f"orders:{user_id}:page={page}:limit={limit}"

  # 3. Redis check
  cached = await shared_redis.get(cache_key)
  if cached:
      return json.loads(cached)

  # 4. DB se fetch — pipeline
  pipeline = [
      {"$match": {"user_id": user_id}},
      {"$sort": {"created_at": -1}},
      {"$facet": {
          "data": [
              {"$skip": skip},
              {"$limit": limit},
              {"$project": {
                  "_id": 0,
                  "order_id": 1,
                  "status": 1,
                  "product.name": 1,
                  "product.quantity": 1,
                  "product.total_price": 1,
                  "payment.method": 1,
                  "payment.status": 1,
                  "created_at": 1,
              }}
          ],
          "total": [{"$count": "count"}]
      }}
  ]

  result = await order_collection.aggregate(pipeline).to_list(length=1)
  result = result[0] if result else {"data": [], "total": []}

  orders = result["data"]
  total = result["total"][0]["count"] if result["total"] else 0

  response_data = {
      "data": orders,
      "pagination": {
          "page": page,
          "limit": limit,
          "total": total,
          "total_pages": -(-total // limit),
          "has_next": (page * limit) < total,
          "has_prev": page > 1,
      }
  }

  # 5. Redis mein save karo — 5 min
  await shared_redis.setex(
      cache_key,
      5 * 60,
      json.dumps(response_data, default=str)
  )

  return response_data


# Get Order By Id
@router.get("/{order_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def order(
    request: Request,
    order_id: str,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user dekh sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user order dekh sakta hai"
      )
  user_id = user.get("id")

  # 1. Redis check
  cached = await shared_redis.get(f"order:{order_id}")
  if cached:
      order_data = json.loads(cached)
      # Apna order hai?
      if order_data.get("user_id") != user_id:
          raise HTTPException(
              status_code=status.HTTP_403_FORBIDDEN,
              detail="Ye aapka order nahi hai"
          )
      return order_data

  # 2. DB se fetch
  order_data = await order_collection.find_one(
      {"order_id": order_id, "user_id": user_id},
      {
          "_id": 0,
          "order_id": 1,
          "status": 1,
          "product": 1,
          "shipping_address": 1,
          "payment": 1,
          "created_at": 1,
      }
  )

  if not order_data:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Order nahi mila"
      )

  # 3. Redis mein save karo
  await shared_redis.setex(
      f"order:{order_id}",
      7 * 24 * 60 * 60,
      json.dumps(order_data, default=str)
  )

  return order_data


# Update Order User Only Allow To Do Cancle Order
@router.put("/{order_id}/cancel", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def update_order(
    request: Request,
    order_id: str,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user cancel kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user order cancel kar sakta hai"
      )

  user_id = user.get("id")

  # find one and update
  order_data = await order_collection.find_one_and_update(
      {
          "order_id": order_id,
          "user_id": user_id,
          "status": {"$nin": ["cancelled", "delivered"]}  # sirf ye status pe cancel hoga
      },
      {"$set": {"status": "cancelled"}},
      projection={"_id": 0, "status": 1},
      return_document=False  # purana document return karo (update se pehle wala)
  )

  if not order_data:
    # Ya order mila nahi, ya already cancelled/delivered hai
    existing = await order_collection.find_one(
        {"order_id": order_id, "user_id": user_id},
        {"_id": 0, "status": 1}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Order nahi mila")
    raise HTTPException(
        status_code=400,
        detail=f"Order already {existing['status']} hai"
    )

  # 5. Redis cache update karo
  cached = await shared_redis.get(f"order:{order_id}")
    
  if cached:
      order_cache = json.loads(cached)
      order_cache["status"] = "cancelled"
      await shared_redis.setex(
          f"order:{order_id}",
          7 * 24 * 60 * 60,
          json.dumps(order_cache)
      )
      
  await publish_event(
    "neuralmcart.order.cancelled",
    {
        "order_id": order_id,
        "user_id": user_id
    }
  )

  return {"message": "Order cancel ho gaya", "order_id": order_id}


# Delete Order
@router.delete("/delete/{order_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def delete_order(
    request: Request,
    order_id: str,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf admin delete kar sakta hai
  if user.get("role") != "admin":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf admin order delete kar sakta hai"
      )

  # 2. DB se delete karo
  result = await order_collection.delete_one({"order_id": order_id})

  if result.deleted_count == 0:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Order nahi mila"
      )

  # 3. Redis se hatao
  await shared_redis.delete(f"order:{order_id}")

  return {"message": "Order delete ho gaya", "order_id": order_id}


