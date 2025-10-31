from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer
from ..config.database import get_db
from ..models.schemas import OrderResponse, OrderCreate, OrderUpdate
from ..utils.auth import get_current_user_from_token

router = APIRouter(prefix="/api/orders", tags=["Orders"])
security = HTTPBearer()


def get_current_user_token(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db)
):
    """Extract user info from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.replace("Bearer ", "")
    return get_current_user_from_token(token, db)


# ------------------------------------------------------
# ✅ Create an order (customer only)
# ------------------------------------------------------
@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Customers create an order for a product"""
    try:
        if current_user["role"] != "customer":
            raise HTTPException(status_code=403, detail="Only customers can create orders")

        result = db.run(
            """
            MATCH (c:User {email: $email}), (p:Product)
            WHERE elementId(p) = $product_id AND p.is_available = true
            CREATE (o:Order {
                quantity: $quantity,
                status: 'pending',
                created_at: datetime()
            })
            CREATE (c)-[:PLACED]->(o)
            CREATE (o)-[:FOR_PRODUCT]->(p)
            RETURN o, p
            """,
            email=current_user["email"],
            product_id=order_data.product_id,
            quantity=order_data.quantity,
        )

        record = result.single()
        if not record:
            raise HTTPException(status_code=400, detail="Failed to create order")

        o = record["o"]
        return OrderResponse(
            id=str(o.id),
            status=o["status"],
            quantity=o["quantity"],
            created_at=str(o["created_at"]),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Get logged-in baker's related orders
# ------------------------------------------------------
@router.get("/baker/me", response_model=List[OrderResponse])
async def get_baker_orders(
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Return all orders that include baker’s products"""
    try:
        if current_user["role"] != "baker":
            raise HTTPException(status_code=403, detail="Access denied: Not a baker")

        result = db.run(
            """
            MATCH (b:User {email: $email})-[:BAKES]->(p:Product)<-[:FOR_PRODUCT]-(o:Order)
            OPTIONAL MATCH (c:User)-[:PLACED]->(o)
            RETURN o, p, c
            ORDER BY o.created_at DESC
            """,
            email=current_user["email"]
        )

        orders = []
        for record in result:
            o = record["o"]
            p = record["p"]
            c = record.get("c")

            orders.append(
                OrderResponse(
                    id=str(o.id),
                    status=o.get("status", "pending"),
                    quantity=o.get("quantity", 0),
                    created_at=str(o.get("created_at")),
                    product_name=p["name"],
                    customer_name=c["name"] if c else None,
                )
            )

        return orders

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Get all orders (admin only)
# ------------------------------------------------------
@router.get("/admin/all", response_model=List[OrderResponse])
async def get_all_orders(
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Admins get all orders"""
    try:
        if current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admins only")

        result = db.run(
            """
            MATCH (o:Order)-[:FOR_PRODUCT]->(p:Product)
            OPTIONAL MATCH (c:User)-[:PLACED]->(o)
            OPTIONAL MATCH (b:User)-[:BAKES]->(p)
            RETURN o, p, c, b
            ORDER BY o.created_at DESC
            """
        )

        orders = []
        for record in result:
            o = record["o"]
            p = record["p"]
            c = record.get("c")
            b = record.get("b")

            orders.append(
                OrderResponse(
                    id=str(o.id),
                    status=o["status"],
                    quantity=o["quantity"],
                    created_at=str(o["created_at"]),
                    product_name=p["name"],
                    customer_name=c["name"] if c else None,
                    baker_name=b["name"] if b else None,
                )
            )

        return orders

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Update order status (baker or admin)
# ------------------------------------------------------
@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_update: OrderUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Allow baker or admin to update an order status"""
    try:
        if current_user["role"] not in ["baker", "admin"]:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.run(
            """
            MATCH (o:Order)
            WHERE elementId(o) = $order_id
            SET o.status = $status, o.updated_at = datetime()
            RETURN o
            """,
            order_id=order_id,
            status=status_update.status,
        )

        return {"message": "Order status updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
