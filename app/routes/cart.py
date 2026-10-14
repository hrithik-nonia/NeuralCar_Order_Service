from fastapi import APIRouter, status, Request, Depends, Query
from app.utils.limiter import limiter
from app.utils.dependency import get_current_user


router = APIRouter(prefix="/cart", tags=["Cart APIs"])

# Create Cart
@router.post("/add/{product_id}", status_code= status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_cart(request: Request, product_id: str, quantity: int, user: dict = Depends(get_current_user))-> dict | None:
  pass


# Get All Cart Data
@router.get("/products", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def carts(request: Request, page: int = Query(default=1, ge=1), limit: int = Query(default=10, ge=1, le=100), user: dict = Depends(get_current_user)):
  pass


# Get Cart By Id
@router.get("/{cart_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def cart(request: Request, cart_id: str, user: dict = Depends(get_current_user)):
  pass

# Update Cart Only Quantity Is Mutable
@router.put("/{cart_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def update_cart(request: Request, cart_id: str, user: dict = Depends(get_current_user)):
  pass


# Delete Single Cart Data
@router.delete("/remove/{cart_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def remove_cart(request: Request, cart_id: str, user: dict = Depends(get_current_user)):
  pass

# Delete All Cart Data
@router.delete("/clear", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def clear_cart(request: Request, user: dict = Depends(get_current_user)):
  pass