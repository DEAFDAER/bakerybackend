from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer
from ..config.database import get_db
from ..models.schemas import ProductCreate, ProductUpdate, ProductResponse
from ..utils.auth import get_current_user_from_token

router = APIRouter(prefix="/api/products", tags=["Products"])
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
# ✅ Create a product (linked automatically to baker)
# ------------------------------------------------------
@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Create a new product for the logged-in baker"""
    try:
        if current_user["role"] != "baker":
            raise HTTPException(status_code=403, detail="Only bakers can create products")

        result = db.run(
            """
            MATCH (b:User {email: $email})
            CREATE (p:Product {
                name: $name,
                description: $description,
                price: $price,
                stock_quantity: $stock_quantity,
                is_available: true,
                created_at: datetime()
            })
            CREATE (b)-[:BAKES]->(p)
            RETURN p
            """,
            email=current_user["email"],
            **product_data.dict()
        )

        record = result.single()
        if not record:
            raise HTTPException(status_code=500, detail="Failed to create product")

        p = record["p"]
        return ProductResponse(
            id=str(p.id),
            name=p["name"],
            description=p.get("description"),
            price=p["price"],
            stock_quantity=p["stock_quantity"],
            is_available=p["is_available"],
            created_at=str(p["created_at"])
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Get only the logged-in baker’s products
# ------------------------------------------------------
@router.get("/baker/me", response_model=List[ProductResponse])
async def get_baker_products(
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Return only the baker’s own products"""
    try:
        if current_user["role"] != "baker":
            raise HTTPException(status_code=403, detail="Access denied: Not a baker")

        result = db.run(
            """
            MATCH (b:User {email: $email})-[:BAKES]->(p:Product)
            RETURN p ORDER BY p.created_at DESC
            """,
            email=current_user["email"]
        )

        products = []
        for record in result:
            p = record["p"]
            products.append(
                ProductResponse(
                    id=str(p.id),
                    name=p["name"],
                    description=p.get("description"),
                    price=p["price"],
                    stock_quantity=p["stock_quantity"],
                    is_available=p["is_available"],
                    created_at=str(p["created_at"])
                )
            )

        return products

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Public - Get all available products
# ------------------------------------------------------
@router.get("/", response_model=List[ProductResponse])
async def get_products(
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db=Depends(get_db)
):
    """Get all available products with optional filters"""
    try:
        query = ["MATCH (p:Product) WHERE p.is_available = true"]
        params = {}

        if search:
            query.append("(p.name CONTAINS $search OR p.description CONTAINS $search)")
            params["search"] = search
        if min_price is not None:
            query.append("p.price >= $min_price")
            params["min_price"] = min_price
        if max_price is not None:
            query.append("p.price <= $max_price")
            params["max_price"] = max_price

        cypher = "MATCH (p:Product) WHERE " + " AND ".join(query[1:]) + " RETURN p ORDER BY p.created_at DESC"
        result = db.run(cypher, **params)

        products = []
        for record in result:
            p = record["p"]
            products.append(
                ProductResponse(
                    id=str(p.id),
                    name=p["name"],
                    description=p.get("description"),
                    price=p["price"],
                    stock_quantity=p["stock_quantity"],
                    is_available=p["is_available"],
                    created_at=str(p["created_at"])
                )
            )

        return products

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Update product
# ------------------------------------------------------
@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Update a product (baker or admin only)"""
    try:
        # Ensure baker owns the product
        result = db.run(
            """
            MATCH (b:User {email: $email})-[:BAKES]->(p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
            """,
            email=current_user["email"],
            product_id=product_id
        )

        if not result.single():
            raise HTTPException(status_code=404, detail="Product not found or not owned by baker")

        updates = {k: v for k, v in product_data.dict().items() if v is not None}
        set_clause = ", ".join([f"p.{k} = ${k}" for k in updates.keys()])

        db.run(
            f"""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            SET {set_clause}, p.updated_at = datetime()
            RETURN p
            """,
            product_id=product_id,
            **updates
        )

        result = db.run(
            """
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
            """,
            product_id=product_id
        )

        record = result.single()
        p = record["p"]
        return ProductResponse(
            id=str(p.id),
            name=p["name"],
            description=p.get("description"),
            price=p["price"],
            stock_quantity=p["stock_quantity"],
            is_available=p["is_available"],
            created_at=str(p["created_at"])
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------
# ✅ Soft delete (mark unavailable)
# ------------------------------------------------------
@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Mark a product as unavailable"""
    try:
        db.run(
            """
            MATCH (b:User {email: $email})-[:BAKES]->(p:Product)
            WHERE elementId(p) = $product_id
            SET p.is_available = false, p.updated_at = datetime()
            RETURN p
            """,
            email=current_user["email"],
            product_id=product_id
        )
        return {"message": "Product marked as unavailable"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
