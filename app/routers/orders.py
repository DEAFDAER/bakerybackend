from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from datetime import datetime, timedelta

from ..config.database import get_db
from ..models.schemas import OrderCreate, OrderUpdate, OrderResponse, OrderItemCreate, ProductResponse, UserResponse, UserRole, OrderStatus
from ..utils.auth import get_current_user_from_token

router = APIRouter()


def get_current_user_token(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db)
):
    """Extract token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    return get_current_user_from_token(token, db)


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_token)
):
    """Create a new order"""
    try:
        if not order_data.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order must contain at least one item"
            )

        # Calculate order totals
        total_amount = 0
        tax_rate = 0.12  # 12% tax for Philippines

        # Create order items and calculate totals
        order_items = []
        for item_data in order_data.items:
            # Find product by name
            product_result = db.run("""
                MATCH (p:Product {name: $product_name, is_available: true})
                RETURN p
            """, product_name=item_data.product_name)

            product_record = product_result.single()
            if not product_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {item_data.product_name} not found or unavailable"
                )

            product_data = product_record["p"]

            if product_data["stock_quantity"] < item_data.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product {product_data['name']}"
                )

            item_total = product_data["price"] * item_data.quantity
            total_amount += item_total

            # Create order item
            order_item_props = {
                "product_name": item_data.product_name,
                "quantity": item_data.quantity,
                "unit_price": product_data["price"],
                "total_price": item_total,
                "created_at": "datetime()"
            }

            order_items.append({
                "product_id": str(product_data.id),
                "props": order_item_props
            })

            # Update stock
            db.run("""
                MATCH (p:Product {name: $product_name})
                SET p.stock_quantity = p.stock_quantity - $quantity
            """, product_name=item_data.product_name, quantity=item_data.quantity)

        # Calculate final amounts
        delivery_fee = 50.0  # Fixed delivery fee for Bongao Province
        tax_amount = total_amount * tax_rate
        final_amount = total_amount + delivery_fee + tax_amount

        # Create order - use default customer if not authenticated
        customer_email = current_user["email"] if current_user else "customer@example.com"
        
        # Ensure customer exists (create if needed)
        db.run("""
            MERGE (c:User {email: $customer_email})
            ON CREATE SET 
                c.username = 'guest',
                c.full_name = 'Guest Customer',
                c.role = 'customer',
                c.is_active = true,
                c.hashed_password = '',
                c.created_at = datetime()
        """, customer_email=customer_email)
        
        order_props = {
            "total_amount": total_amount,
            "delivery_fee": delivery_fee,
            "tax_amount": tax_amount,
            "final_amount": final_amount,
            "delivery_address": order_data.delivery_address,
            "delivery_instructions": order_data.delivery_instructions,
            "status": "pending",
            "estimated_delivery_time": str(datetime.utcnow() + timedelta(hours=2)),
            "created_at": "datetime()"
        }

        # Create order with items in Neo4j
        result = db.run("""
            MATCH (c:User {email: $customer_email})
            CREATE (o:Order {
                total_amount: $total_amount,
                delivery_fee: $delivery_fee,
                tax_amount: $tax_amount,
                final_amount: $final_amount,
                delivery_address: $delivery_address,
                delivery_instructions: $delivery_instructions,
                status: $status,
                estimated_delivery_time: $estimated_delivery_time,
                created_at: datetime()
            })
            CREATE (c)-[:PLACED]->(o)
            RETURN o, c
        """, customer_email=customer_email, **order_props)

        order_record = result.single()
        if not order_record:
            raise HTTPException(status_code=500, detail="Failed to create order")

        order_node = order_record["o"]
        customer_node = order_record["c"]

        # Create order items and relationships
        order_item_responses = []
        for i, item in enumerate(order_items):
            item_result = db.run("""
                MATCH (o:Order), (p:Product {name: $product_name})
                WHERE elementId(o) = $order_id
                CREATE (oi:OrderItem {
                    product_name: $product_name,
                    quantity: $quantity,
                    unit_price: $unit_price,
                    total_price: $total_price,
                    created_at: datetime()
                })
                CREATE (o)-[:CONTAINS]->(oi)
                CREATE (oi)-[:PRODUCT]->(p)
                RETURN oi, p
            """, order_id=str(order_node.id),
                 product_name=item["props"]["product_name"],
                 **item["props"])

            item_record = item_result.single()
            if item_record:
                item_node = item_record["oi"]
                product_node = item_record["p"]

                order_item_responses.append({
                    "id": str(item_node.id),
                    "product_name": item["props"]["product_name"],
                    "quantity": item["props"]["quantity"],
                    "unit_price": item["props"]["unit_price"],
                    "total_price": item["props"]["total_price"],
                    "product": ProductResponse(
                        id=str(product_node.id),
                        name=product_node["name"],
                        description=product_node.get("description"),
                        price=product_node["price"],
                        stock_quantity=product_node["stock_quantity"],
                        is_available=product_node["is_available"],
                        created_at=str(product_node["created_at"]),
                        category=None  # Would need to fetch category separately
                    )
                })

        # Return order response
        return OrderResponse(
            id=str(order_node.id),
            total_amount=order_node["total_amount"],
            delivery_fee=order_node.get("delivery_fee", 50.0),
            tax_amount=order_node.get("tax_amount", 0.0),
            final_amount=order_node["final_amount"],
            status=OrderStatus(order_node["status"]),
            delivery_address=order_node["delivery_address"],
            delivery_instructions=order_node.get("delivery_instructions"),
            created_at=str(order_node["created_at"]),
            customer=UserResponse(
                id=str(customer_node.id),
                email=customer_node["email"],
                username=customer_node["username"],
                full_name=customer_node["full_name"],
                phone=customer_node.get("phone"),
                address=customer_node.get("address"),
                role=UserRole(customer_node["role"]),
                is_active=customer_node["is_active"],
                created_at=str(customer_node["created_at"])
            ),
            items=order_item_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")


@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    status_filter: Optional[OrderStatus] = None,
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Get orders for current user"""
    try:
        # If no user is authenticated, return empty list
        if not current_user:
            return []
        
        customer_email = current_user["email"]

        if status_filter:
            result = db.run("""
                MATCH (c:User {email: $customer_email})-[:PLACED]->(o:Order)
                WHERE o.status = $status
                OPTIONAL MATCH (o)-[:CONTAINS]->(oi:OrderItem)-[:PRODUCT]->(p:Product)
                RETURN o, c, oi, p
                ORDER BY o.created_at DESC
                SKIP $skip LIMIT $limit
            """, customer_email=customer_email, status=status_filter.value, skip=skip, limit=limit)
        else:
            result = db.run("""
                MATCH (c:User {email: $customer_email})-[:PLACED]->(o:Order)
                OPTIONAL MATCH (o)-[:CONTAINS]->(oi:OrderItem)-[:PRODUCT]->(p:Product)
                RETURN o, c, oi, p
                ORDER BY o.created_at DESC
                SKIP $skip LIMIT $limit
            """, customer_email=customer_email, skip=skip, limit=limit)

        orders_dict = {}
        for record in result:
            order_node = record["o"]
            order_id = str(order_node.id)

            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    "order": order_node,
                    "customer": record["c"],
                    "items": []
                }

            if record.get("oi") and record.get("p"):
                item_node = record["oi"]
                product_node = record["p"]

                orders_dict[order_id]["items"].append({
                    "id": str(item_node.id),
                    "product_name": item_node["product_name"],
                    "quantity": item_node["quantity"],
                    "unit_price": item_node["unit_price"],
                    "total_price": item_node["total_price"],
                    "product": ProductResponse(
                        id=str(product_node.id),
                        name=product_node["name"],
                        description=product_node.get("description"),
                        price=product_node["price"],
                        stock_quantity=product_node["stock_quantity"],
                        is_available=product_node["is_available"],
                        created_at=str(product_node["created_at"]),
                        category=None
                    )
                })

        orders = []
        for order_data in orders_dict.values():
            order_node = order_data["order"]
            customer_node = order_data["customer"]

            orders.append(OrderResponse(
                id=str(order_node.id),
                total_amount=order_node["total_amount"],
                delivery_fee=order_node.get("delivery_fee", 50.0),
                tax_amount=order_node.get("tax_amount", 0.0),
                final_amount=order_node["final_amount"],
                status=OrderStatus(order_node["status"]),
                delivery_address=order_node["delivery_address"],
                delivery_instructions=order_node.get("delivery_instructions"),
                created_at=str(order_node["created_at"]),
                customer=UserResponse(
                    id=str(customer_node.id),
                    email=customer_node["email"],
                    username=customer_node["username"],
                    full_name=customer_node["full_name"],
                    phone=customer_node.get("phone"),
                    address=customer_node.get("address"),
                    role=UserRole(customer_node["role"]),
                    is_active=customer_node["is_active"],
                    created_at=str(customer_node["created_at"])
                ),
                items=order_data["items"]
            ))

        return orders
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db=Depends(get_db)
):
    """Get a specific order"""
    try:
        result = db.run("""
            MATCH (o:Order)
            WHERE elementId(o) = $order_id
            OPTIONAL MATCH (c:User)-[:PLACED]->(o)
            OPTIONAL MATCH (o)-[:CONTAINS]->(oi:OrderItem)-[:PRODUCT]->(p:Product)
            RETURN o, c, oi, p
        """, order_id=order_id)

        records = list(result)
        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        order_node = records[0]["o"]
        customer_node = records[0]["c"]

        # Collect all order items
        items = []
        for record in records:
            if record.get("oi") and record.get("p"):
                item_node = record["oi"]
                product_node = record["p"]

                items.append({
                    "id": str(item_node.id),
                    "product_name": item_node["product_name"],
                    "quantity": item_node["quantity"],
                    "unit_price": item_node["unit_price"],
                    "total_price": item_node["total_price"],
                    "product": ProductResponse(
                        id=str(product_node.id),
                        name=product_node["name"],
                        description=product_node.get("description"),
                        price=product_node["price"],
                        stock_quantity=product_node["stock_quantity"],
                        is_available=product_node["is_available"],
                        created_at=str(product_node["created_at"]),
                        category=None
                    )
                })

        return OrderResponse(
            id=str(order_node.id),
            total_amount=order_node["total_amount"],
            delivery_fee=order_node.get("delivery_fee", 50.0),
            tax_amount=order_node.get("tax_amount", 0.0),
            final_amount=order_node["final_amount"],
            status=OrderStatus(order_node["status"]),
            delivery_address=order_node["delivery_address"],
            delivery_instructions=order_node.get("delivery_instructions"),
            created_at=str(order_node["created_at"]),
            customer=UserResponse(
                id=str(customer_node.id),
                email=customer_node["email"],
                username=customer_node["username"],
                full_name=customer_node["full_name"],
                phone=customer_node.get("phone"),
                address=customer_node.get("address"),
                role=UserRole(customer_node["role"]),
                is_active=customer_node["is_active"],
                created_at=str(customer_node["created_at"])
            ),
            items=items
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_update: OrderUpdate,
    db=Depends(get_db)
):
    """Update order status (for bakers and delivery personnel)"""
    try:
        # Check if order exists
        check_result = db.run("""
            MATCH (o:Order)
            WHERE elementId(o) = $order_id
            RETURN o
        """, order_id=order_id)

        if not check_result.single():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        # Permission checks removed

        # Update order
        update_data = {}
        if status_update.status:
            update_data["status"] = status_update.status.value

        if status_update.delivery_instructions:
            update_data["delivery_instructions"] = status_update.delivery_instructions

        # Set actual delivery time if delivered
        if status_update.status and status_update.status.value == "delivered":
            update_data["actual_delivery_time"] = str(datetime.utcnow())

        if update_data:
            set_clause = ", ".join([f"o.{k} = ${k}" for k in update_data.keys()])
            db.run(f"""
                MATCH (o:Order)
                WHERE elementId(o) = $order_id
                SET {set_clause}, o.updated_at = datetime()
            """, order_id=order_id, **update_data)

        return {"message": "Order status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/all", response_model=List[OrderResponse])
async def get_all_orders(
    status_filter: Optional[OrderStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db)
):
    """Get all orders"""
    try:

        if status_filter:
            result = db.run("""
                MATCH (o:Order)
                WHERE o.status = $status
                OPTIONAL MATCH (c:User)-[:PLACED]->(o)
                OPTIONAL MATCH (o)-[:CONTAINS]->(oi:OrderItem)-[:PRODUCT]->(p:Product)
                RETURN o, c, oi, p
                ORDER BY o.created_at DESC
                SKIP $skip LIMIT $limit
            """, status=status_filter.value, skip=skip, limit=limit)
        else:
            result = db.run("""
                MATCH (o:Order)
                OPTIONAL MATCH (c:User)-[:PLACED]->(o)
                OPTIONAL MATCH (o)-[:CONTAINS]->(oi:OrderItem)-[:PRODUCT]->(p:Product)
                RETURN o, c, oi, p
                ORDER BY o.created_at DESC
                SKIP $skip LIMIT $limit
            """, skip=skip, limit=limit)

        orders_dict = {}
        for record in result:
            order_node = record["o"]
            order_id = str(order_node.id)

            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    "order": order_node,
                    "customer": record.get("c"),
                    "items": []
                }

            if record.get("oi") and record.get("p"):
                item_node = record["oi"]
                product_node = record["p"]

                orders_dict[order_id]["items"].append({
                    "id": str(item_node.id),
                    "product_name": item_node["product_name"],
                    "quantity": item_node["quantity"],
                    "unit_price": item_node["unit_price"],
                    "total_price": item_node["total_price"],
                    "product": ProductResponse(
                        id=str(product_node.id),
                        name=product_node["name"],
                        description=product_node.get("description"),
                        price=product_node["price"],
                        stock_quantity=product_node["stock_quantity"],
                        is_available=product_node["is_available"],
                        created_at=str(product_node["created_at"]),
                        category=None
                    )
                })

        orders = []
        for order_data in orders_dict.values():
            order_node = order_data["order"]
            customer_node = order_data.get("customer")

            customer_response = None
            if customer_node:
                customer_response = UserResponse(
                    id=str(customer_node.id),
                    email=customer_node["email"],
                    username=customer_node["username"],
                    full_name=customer_node["full_name"],
                    phone=customer_node.get("phone"),
                    address=customer_node.get("address"),
                    role=UserRole(customer_node["role"]),
                    is_active=customer_node["is_active"],
                    created_at=str(customer_node["created_at"])
                )

            orders.append(OrderResponse(
                id=str(order_node.id),
                total_amount=order_node["total_amount"],
                delivery_fee=order_node.get("delivery_fee", 50.0),
                tax_amount=order_node.get("tax_amount", 0.0),
                final_amount=order_node["final_amount"],
                status=OrderStatus(order_node["status"]),
                delivery_address=order_node["delivery_address"],
                delivery_instructions=order_node.get("delivery_instructions"),
                created_at=str(order_node["created_at"]),
                customer=customer_response,
                items=order_data["items"]
            ))

        return orders
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
