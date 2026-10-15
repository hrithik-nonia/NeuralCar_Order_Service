import httpx
import os
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")


async def get_product(product_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{PRODUCT_SERVICE_URL}/product/{product_id}"
            )

        # Product nahi mila
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product nahi mila"
            )

        # Koi aur error
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Product service error"
            )

        product = response.json()

        # Product active hai?
        if not product.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product available nahi hai"
            )

        # Stock hai?
        if product.get("stock", 0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product out of stock hai"
            )

        return product

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product service timeout"
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product service unavailable"
        )