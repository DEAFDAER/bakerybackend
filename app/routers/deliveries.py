from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from datetime import datetime

from ..config.database import get_db
from ..models.schemas import DeliveryCreate, DeliveryUpdate, DeliveryResponse, UserResponse, UserRole, OrderStatus, OrderResponse
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


@router.post("/", response_model=DeliveryResponse)
async def create_delivery(
    delivery_data: DeliveryCreate,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Create a new delivery assignment"""
    try:
        # Authorization check removed
        pass

        # Verify order exists and is ready for delivery
        order_result = db.run("""
            MATCH (o:Order)
            WHERE elementId(o) = $order_id
            RETURN o
        """, order_id=delivery_data.order_id)

        order_record = order_result.single()
        if not order_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        order_node = order_record["o"]

        if order_node["status"] not in ["ready", "out_for_delivery"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order must be ready for delivery"
            )

        # Verify delivery person if specified
        delivery_person = None
        if delivery_data.delivery_person_id:
            dp_result = db.run("""
                MATCH (u:User)
                WHERE elementId(u) = $delivery_person_id
                    AND u.role = $role
                    AND u.is_active = true
                RETURN u
            """, delivery_person_id=delivery_data.delivery_person_id, role="delivery_person")

            delivery_person_record = dp_result.single()
            if not delivery_person_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Delivery person not found or inactive"
                )

            delivery_person = delivery_person_record["u"]

        # Create delivery record
        delivery_props = {
            "status": "assigned",
            "delivery_notes": delivery_data.delivery_notes,
            "assigned_at": str(datetime.utcnow())
        }

        result = db.run("""
            MATCH (o:Order), (dp:User)
            WHERE elementId(o) = $order_id
                AND (dp IS NULL OR elementId(dp) = $delivery_person_id)
            CREATE (d:Delivery {
                status: $status,
                delivery_notes: $delivery_notes,
                assigned_at: datetime()
            })
            CREATE (d)-[:ASSIGNED_TO]->(o)
            CREATE (dp)-[:ASSIGNED]->(d)
            RETURN d, o, dp
        """, order_id=delivery_data.order_id,
             delivery_person_id=delivery_data.delivery_person_id,
             **delivery_props)

        delivery_record = result.single()
        if not delivery_record:
            raise HTTPException(status_code=500, detail="Failed to create delivery")

        delivery_node = delivery_record["d"]
        order_node = delivery_record["o"]
        delivery_person_node = delivery_record.get("dp")

        # Update order status
        db.run("""
            MATCH (o:Order)
            WHERE elementId(o) = $order_id
            SET o.status = $status, o.updated_at = datetime()
        """, order_id=delivery_data.order_id, status="out_for_delivery")

        # Return delivery response
        delivery_person_response = None
        if delivery_person_node:
            delivery_person_response = UserResponse(
                id=str(delivery_person_node.id),
                email=delivery_person_node["email"],
                username=delivery_person_node["username"],
                full_name=delivery_person_node["full_name"],
                phone=delivery_person_node.get("phone"),
                address=delivery_person_node.get("address"),
                role=UserRole(delivery_person_node["role"]),
                is_active=delivery_person_node["is_active"],
                created_at=str(delivery_person_node["created_at"])
            )

        return DeliveryResponse(
            id=str(delivery_node.id),
            status=delivery_node["status"],
            delivery_notes=delivery_node.get("delivery_notes"),
            assigned_at=str(delivery_node["assigned_at"]),
            order=OrderResponse(
                id=str(order_node.id),
                total_amount=order_node["total_amount"],
                final_amount=order_node["final_amount"],
                status=OrderStatus(order_node["status"]),
                delivery_address=order_node["delivery_address"],
                delivery_instructions=order_node.get("delivery_instructions"),
                created_at=str(order_node["created_at"]),
                customer=None,  # Would need to fetch customer separately
                items=[]  # Would need to fetch items separately
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[DeliveryResponse])
async def get_deliveries(
    current_user=Depends(get_current_user_token),
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db)
):
    """Get deliveries"""
    try:
        # Authentication check removed
        current_user_role = current_user.get("role") if current_user else None
        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")

        # Build query based on user role
        if current_user_role == "delivery_person":
            if status_filter:
                result = db.run("""
                    MATCH (dp:User {email: $user_email})-[:ASSIGNED]->(d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                    WHERE d.status = $status_filter
                    RETURN d, o, dp
                    ORDER BY d.assigned_at DESC
                    SKIP $skip LIMIT $limit
                """, user_email=current_user["email"], status_filter=status_filter, skip=skip, limit=limit)
            else:
                result = db.run("""
                    MATCH (dp:User {email: $user_email})-[:ASSIGNED]->(d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                    RETURN d, o, dp
                    ORDER BY d.assigned_at DESC
                    SKIP $skip LIMIT $limit
                """, user_email=current_user["email"], skip=skip, limit=limit)
        elif current_user_role in ["admin", "baker"]:
            if status_filter:
                result = db.run("""
                    MATCH (d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                    WHERE d.status = $status_filter
                    OPTIONAL MATCH (dp:User)-[:ASSIGNED]->(d)
                    RETURN d, o, dp
                    ORDER BY d.assigned_at DESC
                    SKIP $skip LIMIT $limit
                """, status_filter=status_filter, skip=skip, limit=limit)
            else:
                result = db.run("""
                    MATCH (d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                    OPTIONAL MATCH (dp:User)-[:ASSIGNED]->(d)
                    RETURN d, o, dp
                    ORDER BY d.assigned_at DESC
                    SKIP $skip LIMIT $limit
                """, skip=skip, limit=limit)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        deliveries_dict = {}
        for record in result:
            delivery_node = record["d"]
            delivery_id = str(delivery_node.id)

            if delivery_id not in deliveries_dict:
                deliveries_dict[delivery_id] = {
                    "delivery": delivery_node,
                    "order": record["o"],
                    "delivery_person": record.get("dp")
                }

        deliveries = []
        for delivery_data in deliveries_dict.values():
            delivery_node = delivery_data["delivery"]
            order_node = delivery_data["order"]
            delivery_person_node = delivery_data.get("delivery_person")

            delivery_person_response = None
            if delivery_person_node:
                delivery_person_response = UserResponse(
                    id=str(delivery_person_node.id),
                    email=delivery_person_node["email"],
                    username=delivery_person_node["username"],
                    full_name=delivery_person_node["full_name"],
                    phone=delivery_person_node.get("phone"),
                    address=delivery_person_node.get("address"),
                    role=UserRole(delivery_person_node["role"]),
                    is_active=delivery_person_node["is_active"],
                    created_at=str(delivery_person_node["created_at"])
                )

            deliveries.append(DeliveryResponse(
                id=str(delivery_node.id),
                status=delivery_node["status"],
                delivery_notes=delivery_node.get("delivery_notes"),
                assigned_at=str(delivery_node["assigned_at"]),
                order=OrderResponse(
                    id=str(order_node.id),
                    total_amount=order_node["total_amount"],
                    final_amount=order_node["final_amount"],
                    status=OrderStatus(order_node["status"]),
                    delivery_address=order_node["delivery_address"],
                    delivery_instructions=order_node.get("delivery_instructions"),
                    created_at=str(order_node["created_at"]),
                    customer=None,
                    items=[]
                )
            ))

        return deliveries
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: str,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Get a specific delivery"""
    try:
        # Authentication check removed
        current_user_role = current_user.get("role") if current_user else None
        current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")

        # Build query based on user role
        if current_user_role == "delivery_person":
            result = db.run("""
                MATCH (dp:User {email: $user_email})-[:ASSIGNED]->(d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                WHERE elementId(d) = $delivery_id
                RETURN d, o, dp
            """, user_email=current_user["email"], delivery_id=delivery_id)
        else:
            result = db.run("""
                MATCH (d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                WHERE elementId(d) = $delivery_id
                OPTIONAL MATCH (dp:User)-[:ASSIGNED]->(d)
                RETURN d, o, dp
            """, delivery_id=delivery_id)

        record = result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found"
            )

        delivery_node = record["d"]
        order_node = record["o"]
        delivery_person_node = record.get("dp")

        # Check permissions for delivery persons
        if current_user_role == "delivery_person" and delivery_person_node:
            dp_id = str(delivery_person_node.id)
            if dp_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        delivery_person_response = None
        if delivery_person_node:
            delivery_person_response = UserResponse(
                id=str(delivery_person_node.id),
                email=delivery_person_node["email"],
                username=delivery_person_node["username"],
                full_name=delivery_person_node["full_name"],
                phone=delivery_person_node.get("phone"),
                address=delivery_person_node.get("address"),
                role=UserRole(delivery_person_node["role"]),
                is_active=delivery_person_node["is_active"],
                created_at=str(delivery_person_node["created_at"])
            )

        return DeliveryResponse(
            id=str(delivery_node.id),
            status=delivery_node["status"],
            delivery_notes=delivery_node.get("delivery_notes"),
            assigned_at=str(delivery_node["assigned_at"]),
            order=OrderResponse(
                id=str(order_node.id),
                total_amount=order_node["total_amount"],
                final_amount=order_node["final_amount"],
                status=OrderStatus(order_node["status"]),
                delivery_address=order_node["delivery_address"],
                delivery_instructions=order_node.get("delivery_instructions"),
                created_at=str(order_node["created_at"]),
                customer=None,
                items=[]
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{delivery_id}/status")
async def update_delivery_status(
    delivery_id: str,
    delivery_update: DeliveryUpdate,
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Update delivery status"""
    try:
        # Authentication check removed
        # Get delivery with delivery person info
        result = db.run("""
            MATCH (d:Delivery)
            WHERE elementId(d) = $delivery_id
            OPTIONAL MATCH (dp:User)-[:ASSIGNED]->(d)
            RETURN d, dp
        """, delivery_id=delivery_id)

        record = result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found"
            )

        delivery_node = record["d"]
        delivery_person_node = record.get("dp")

        # Check permissions
        if current_user.get("role") == "delivery_person" and delivery_person_node:
            dp_id = str(delivery_person_node.id)
            current_user_id = str(current_user["id"]) if isinstance(current_user.get("id"), int) else current_user.get("id")
            if dp_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only update your own deliveries"
                )

        # Update delivery
        update_data = {}
        if delivery_update.status:
            update_data["status"] = delivery_update.status

            # Update timestamps based on status
            if delivery_update.status == "picked_up":
                update_data["picked_up_at"] = str(datetime.utcnow())
            elif delivery_update.status == "delivered":
                update_data["delivered_at"] = str(datetime.utcnow())

                # Update order status to delivered
                db.run("""
                    MATCH (d:Delivery)-[:ASSIGNED_TO]->(o:Order)
                    WHERE elementId(d) = $delivery_id
                    SET o.status = $status, o.actual_delivery_time = datetime(), o.updated_at = datetime()
                """, delivery_id=delivery_id, status="delivered")

        if delivery_update.delivery_notes:
            update_data["delivery_notes"] = delivery_update.delivery_notes

        if delivery_update.location_latitude and delivery_update.location_longitude:
            update_data["location_latitude"] = delivery_update.location_latitude
            update_data["location_longitude"] = delivery_update.location_longitude

        if update_data:
            set_clause = ", ".join([f"d.{k} = ${k}" for k in update_data.keys()])
            db.run(f"""
                MATCH (d:Delivery)
                WHERE elementId(d) = $delivery_id
                SET {set_clause}, d.updated_at = datetime()
            """, delivery_id=delivery_id, **update_data)

        return {"message": "Delivery status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available/personnel")
async def get_available_delivery_personnel(
    current_user=Depends(get_current_user_token),
    db=Depends(get_db)
):
    """Get available delivery personnel"""
    try:
        # Authorization check removed
        pass

        # Get all delivery personnel
        result = db.run("""
            MATCH (u:User {role: $role, is_active: true})
            RETURN u
        """, role="delivery_person")

        available_personnel = []
        for record in result:
            person_node = record["u"]

            # Check active deliveries for this person
            active_count_result = db.run("""
                MATCH (u:User)-[:ASSIGNED]->(d:Delivery)
                WHERE elementId(u) = $user_id
                    AND d.status IN ['assigned', 'picked_up', 'in_transit']
                RETURN count(d) as active_count
            """, user_id=str(person_node.id))

            active_count_record = active_count_result.single()
            active_count = active_count_record["active_count"] if active_count_record else 0

            if active_count == 0:
                available_personnel.append({
                    "id": str(person_node.id),
                    "full_name": person_node["full_name"],
                    "phone": person_node.get("phone"),
                    "active_deliveries": active_count
                })

        return available_personnel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
