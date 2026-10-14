from fastapi import APIRouter, Request, status, Depends, Query
from app.utils.limiter import limiter
from app.models.order import OrderCreateInput
from app.utils.dependency import get_current_user

router = APIRouter(prefix="/Order", tags=["Order APIs"])

# Create Order
@router.post("/add/{product_id}", status_code= status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def add_order(request: Request, order_data: OrderCreateInput, product_id: str, user: dict = Depends(get_current_user))-> dict | None:
  pass


# Get Orders
@router.get("/all-orders", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def all_orders(request: Request, page: int = Query(default=1, ge=1), limit: int = Query(default=10, ge=1, le=100), user: dict = Depends(get_current_user)):
  pass


# Get Order By Id
@router.get("/{order_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def order(request: Request, order_id: str, user: dict = Depends(get_current_user)):
  pass


# Update Order User Only Allow To Do Cancle Order
@router.put("/{order_id}/cancel", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def update_order(request: Request, order_id: str, user: dict = Depends(get_current_user)):
  pass


# Delete Order
@router.delete("/delete/{order_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def delete_order(request: Request, order_id: str, user: dict = Depends(get_current_user)):
  pass
