from fastapi import APIRouter, Request, status, Depends
from app.utils.limiter import limiter
from app.models.order import OrderCreateInput
from app.utils.dependency import get_current_user

router = APIRouter(prefix="/Order", tags=["Order APIs"])

# Create Order
@router.post("/add/{product_id}", status_code= status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def add_order(request: Request, order_data: OrderCreateInput, product_id: str, user: dict = Depends(get_current_user))-> dict | None:
  pass


# 
