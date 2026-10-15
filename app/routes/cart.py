from fastapi import APIRouter, status, Request, Depends, Query, HTTPException
from app.utils.limiter import limiter
from app.utils.dependency import get_current_user
from app.utils.product_client import get_product
from app.redis import shared_redis
import json


router = APIRouter(prefix="/cart", tags=["Cart APIs"])

# Create Cart
@router.post("/add/{product_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_cart(
    request: Request,
    product_id: str,
    quantity: int,
    user: dict = Depends(get_current_user)
) -> dict:

    # 1. Sirf user add kar sakta hai
    if user.get("role") != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sirf user cart mein add kar sakta hai"
        )

    # 2. Quantity valid hai?
    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity kam se kam 1 honi chahiye"
        )

    # 3. Product Service se product lo
    product = await get_product(product_id)

    # 4. Quantity stock se zyada nahi honi chahiye
    if quantity > product.get("stock", 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sirf {product['stock']} units available hain"
        )

    # 5. Redis se existing cart lo
    user_id = user.get("id")
    cart_key = f"cart:{user_id}"
    cached_cart = await shared_redis.get(cart_key)

    cart = json.loads(cached_cart) if cached_cart else {"items": []}

    # 6. Product already cart mein hai?
    existing_item = None
    for item in cart["items"]:
        if item["product_id"] == product_id:
            existing_item = item
            break

    if existing_item:
      new_quantity = existing_item["quantity"] + quantity
      if new_quantity > product.get("stock", 0):
          raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
              detail=f"Sirf {product['stock']} units available hain"
          )
      existing_item["quantity"] = new_quantity
      existing_item["total_price"] = existing_item["price"] * new_quantity
    else:
        # Naya item add karo
        cart["items"].append({
            "product_id": product_id,
            "name": product["name"],
            "image": product.get("image"),
            "price": product.get("sale_price") or product["price"],
            "quantity": quantity,
            "total_price": (product.get("sale_price") or product["price"]) * quantity
        })

    # 7. Redis mein save karo — 7 days
    await shared_redis.setex(
        cart_key,
        15 * 24 * 60 * 60,
        json.dumps(cart)
    )

    return {
        "message": "Cart mein add ho gaya",
        "cart": cart
    }


# Get All Cart Data
@router.get("/products", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def carts(
    request: Request,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user add kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user cart dekh sakta hai"
      )
      
  user_id = user.get("id")
  cart_key = f"cart:{user_id}"

  cached_cart = await shared_redis.get(cart_key)

  if not cached_cart:
      return {"items": [], "total_items": 0, "total_price": 0}

  cart = json.loads(cached_cart)

  # Total calculate karo
  total_price = sum(item["total_price"] for item in cart.get("items", []))
  total_items = sum(item["quantity"] for item in cart.get("items", []))

  return {
      "items": cart.get("items", []),
      "total_items": total_items,
      "total_price": round(total_price, 2)
  }


# Get Cart By Id
@router.get("/{product_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def cart(
    request: Request,
    product_id: str,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user add kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user cart ka product dekh sakta hai"
      )
  user_id = user.get("id")
  cart_key = f"cart:{user_id}"

  cached_cart = await shared_redis.get(cart_key)
  if not cached_cart:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Cart empty hai"
      )

  cart = json.loads(cached_cart)

  # product_id se item dhoondo
  item = next(
      (i for i in cart.get("items", []) if i["product_id"] == product_id),
      None
  )

  if not item:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Ye product cart mein nahi hai"
      )

  return item

# Update Cart, Only Quantity Is Mutable
@router.put("/{product_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def update_cart(
    request: Request,
    product_id: str,
    quantity: int,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user update kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user cart update kar sakta hai"
      )

  # 2. Quantity valid hai?
  if quantity < 1:
      raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail="Quantity kam se kam 1 honi chahiye"
      )

  user_id = user.get("id")
  cart_key = f"cart:{user_id}"

  cached_cart = await shared_redis.get(cart_key)
  if not cached_cart:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Cart empty hai"
      )

  cart = json.loads(cached_cart)

  # 3. Product cart mein dhoondo
  item = next(
      (i for i in cart["items"] if i["product_id"] == product_id),
      None
  )

  if not item:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Ye product cart mein nahi hai"
      )

  # 4. Quantity aur total_price update karo
  item["quantity"] = item["quantity"] + quantity
  item["total_price"] = round(item["price"] * item["total_price"], 2)

  # 5. Wapas Redis mein save karo
  await shared_redis.setex(
      cart_key,
      15 * 24 * 60 * 60,
      json.dumps(cart)
  )

  return {"message": "Cart update ho gaya", "cart": cart}



# Delete Single Cart Data
@router.delete("/remove/{product_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def remove_cart(
    request: Request,
    product_id: str,
    user: dict = Depends(get_current_user)
):
  # 1. Sirf user add kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user cart dekh sakta hai"
      )
  user_id = user.get("id")
  cart_key = f"cart:{user_id}"

  cached_cart = await shared_redis.get(cart_key)
  if not cached_cart:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Cart empty hai"
      )

  cart = json.loads(cached_cart)

  # Item dhoondo
  original_count = len(cart["items"])
  cart["items"] = [i for i in cart["items"] if i["product_id"] != product_id]

  # Item mila hi nahi
  if len(cart["items"]) == original_count:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Ye product cart mein nahi hai"
      )

  # Wapas save karo
  await shared_redis.setex(
      cart_key,
      15 * 24 * 60 * 60,
      json.dumps(cart)
  )

  return {"message": "Product cart se remove ho gaya", "cart": cart}


# Delete All Cart Data
@router.delete("/clear", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def clear_cart(request: Request, user: dict = Depends(get_current_user)):
  # 1. Sirf user add kar sakta hai
  if user.get("role") != "user":
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Sirf user cart dekh sakta hai"
      )
      
      
  user_id = user.get("id")
  await shared_redis.delete(f"cart:{user_id}")
  return {"message": "Cart clear ho gaya"}

