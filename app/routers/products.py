from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config.database import get_db
from ..models.schemas import ProductCreate, ProductUpdate, ProductResponse, UserRole
from ..utils.auth import get_current_user_from_token

router = APIRouter()
security = HTTPBearer()


def get_current_user_token(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db)
):
    """Extract token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    return get_current_user_from_token(token, db)


# Product endpoints
@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    db=Depends(get_db)
):
    """Create a new product"""
    try:
        # Get baker info
        baker_result = db.run("""
            MATCH (u:User {email: $baker_email})
            RETURN u
        """, baker_email=product_data.baker_email)

        baker = baker_result.single()
        if not baker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Baker not found"
            )

        # Create product
        product_props = {
            "name": product_data.name,
            "description": product_data.description,
            "price": product_data.price,
            "stock_quantity": product_data.stock_quantity,
            "is_available": True,
            "created_at": "datetime()"
        }

        result = db.run("""
            MATCH (b:User {email: $baker_email})
            CREATE (p:Product {
                name: $name,
                description: $description,
                price: $price,
                stock_quantity: $stock_quantity,
                is_available: $is_available,
                created_at: datetime()
            })
            CREATE (b)-[:BAKES]->(p)
            RETURN p
        """, baker_email=product_data.baker_email,
             **product_props)

        record = result.single()
        if not record:
            raise HTTPException(status_code=500, detail="Failed to create product")

        product_node = record["p"]
        return ProductResponse(
            id=str(product_node.id),
            name=product_node["name"],
            description=product_node.get("description"),
            price=product_node["price"],
            stock_quantity=product_node["stock_quantity"],
            is_available=product_node["is_available"],
            created_at=str(product_node["created_at"])
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ProductResponse])
async def get_products(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    db=Depends(get_db)
):
    """Get all available products with optional filtering"""
    try:
        # Start with basic product match
        query_parts = ["MATCH (p:Product)"]
        where_conditions = []
        params = {"skip": skip, "limit": limit}

        # Handle availability filter
        if in_stock is True:
            where_conditions.append("p.is_available = true AND p.stock_quantity > 0")
        elif in_stock is False:
            where_conditions.append("(p.is_available = false OR p.stock_quantity = 0)")
        else:
            where_conditions.append("p.is_available = true")

        # Handle price filters
        if min_price is not None:
            where_conditions.append("p.price >= $min_price")
            params["min_price"] = min_price

        if max_price is not None:
            where_conditions.append("p.price <= $max_price")
            params["max_price"] = max_price

        # Handle search filter
        if search:
            where_conditions.append("(p.name CONTAINS $search OR p.description CONTAINS $search)")
            params["search"] = search

        # Combine WHERE conditions
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))

        query_parts.extend([
            "RETURN p",
            "SKIP $skip LIMIT $limit"
        ])

        query = "\n".join(query_parts)
        result = db.run(query, **params)

        products = []
        for record in result:
            product_node = record["p"]

            products.append(ProductResponse(
                id=str(product_node.id),
                name=product_node["name"],
                description=product_node.get("description"),
                price=product_node["price"],
                stock_quantity=product_node["stock_quantity"],
                is_available=product_node["is_available"],
                created_at=str(product_node["created_at"])
            ))

        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db=Depends(get_db)):
    """Get a specific product by ID"""
    try:
        result = db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id AND p.is_available = true
            RETURN p
        """, product_id=product_id)

        record = result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        product_node = record["p"]

        return ProductResponse(
            id=str(product_node.id),
            name=product_node["name"],
            description=product_node.get("description"),
            price=product_node["price"],
            stock_quantity=product_node["stock_quantity"],
            is_available=product_node["is_available"],
            created_at=str(product_node["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    db=Depends(get_db)
):
    """Update a product"""
    try:
        # Check if product exists
        check_result = db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
        """, product_id=product_id)

        if not check_result.single():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        # Update product properties
        update_props = {}
        if hasattr(product_data, 'name') and product_data.name is not None:
            update_props['name'] = product_data.name
        if hasattr(product_data, 'description') and product_data.description is not None:
            update_props['description'] = product_data.description
        if hasattr(product_data, 'price') and product_data.price is not None:
            update_props['price'] = product_data.price
        if hasattr(product_data, 'stock_quantity') and product_data.stock_quantity is not None:
            update_props['stock_quantity'] = product_data.stock_quantity
        if hasattr(product_data, 'is_available') and product_data.is_available is not None:
            update_props['is_available'] = product_data.is_available

        if update_props:
            set_clause = ", ".join([f"p.{k} = ${k}" for k in update_props.keys()])
            db.run(f"""
                MATCH (p:Product)
                WHERE elementId(p) = $product_id
                SET {set_clause}, p.updated_at = datetime()
            """, product_id=product_id, **update_props)

        # Fetch updated product
        result = db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
        """, product_id=product_id)

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Product not found after update")

        product_node = record["p"]

        return ProductResponse(
            id=str(product_node.id),
            name=product_node["name"],
            description=product_node.get("description"),
            price=product_node["price"],
            stock_quantity=product_node["stock_quantity"],
            is_available=product_node["is_available"],
            created_at=str(product_node["created_at"])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db=Depends(get_db)
):
    """Soft delete a product (mark as unavailable)"""
    try:
        # First get the product details
        get_result = db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
        """, product_id=product_id)

        product_record = get_result.single()
        if not product_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        # Soft delete by marking as unavailable
        db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            SET p.is_available = false, p.updated_at = datetime()
            RETURN p
        """, product_id=product_id)

        result = db.run("""
            MATCH (p:Product)
            WHERE elementId(p) = $product_id
            RETURN p
        """, product_id=product_id)

        if not result.single():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found after update"
            )

        return {"message": "Product deleted successfully", "deleted_product_id": product_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/all", response_model=List[ProductResponse])
async def get_all_products(
    include_unavailable: bool = False,
    skip: int = 0,
    limit: int = 100,
    db=Depends(get_db)
):
    """Get all products (admin only - includes unavailable products)"""
    try:
        # Build query dynamically based on filters
        query_parts = ["MATCH (p:Product)"]
        params = {"skip": skip, "limit": limit}

        if not include_unavailable:
            query_parts.append("WHERE p.is_available = true")

        query_parts.extend([
            "RETURN p",
            "ORDER BY p.created_at DESC",
            "SKIP $skip LIMIT $limit"
        ])

        query = "\n".join(query_parts)
        result = db.run(query, **params)

        products = []
        for record in result:
            product_node = record["p"]

            products.append(ProductResponse(
                id=str(product_node.id),
                name=product_node["name"],
                description=product_node.get("description"),
                price=product_node["price"],
                stock_quantity=product_node["stock_quantity"],
                is_available=product_node["is_available"],
                created_at=str(product_node["created_at"])
            ))

        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/baker/me", response_model=List[ProductResponse])
async def get_my_products(current_user=Depends(get_current_user_token), db=Depends(get_db)):
    """Get all products created by the logged-in baker"""
    if not current_user or current_user.get("role") != "baker":
        raise HTTPException(status_code=403, detail="Not authorized")

    email = current_user["email"]
    result = db.run("""
        MATCH (b:User {email: $email})-[:BAKES]->(p:Product)
        RETURN p ORDER BY p.created_at DESC
    """, email=email)

    products = []
    for record in result:
        p = record["p"]
        products.append(ProductResponse(
            id=str(p.element_id),
            name=p["name"],
            description=p.get("description"),
            price=p["price"],
            stock_quantity=p["stock_quantity"],
            is_available=p["is_available"],
            created_at=str(p["created_at"])
        ))
    return products
