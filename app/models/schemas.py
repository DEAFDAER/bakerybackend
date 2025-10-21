from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from enum import Enum


class UserRole(str, Enum):
    customer = "customer"
    baker = "baker"
    delivery_person = "delivery_person"
    admin = "admin"


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    preparing = "preparing"
    ready = "ready"
    picked_up = "picked_up"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.customer


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class UserResponse(UserBase):
    id: str
    role: UserRole
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Product Schemas
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock_quantity: int = 0
    image_url: Optional[str] = None


class ProductCreate(ProductBase):
    baker_email: str


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    is_available: Optional[bool] = None


class ProductResponse(ProductBase):
    id: str
    is_available: bool
    created_at: str

    class Config:
        from_attributes = True


# Order Schemas
class OrderItemBase(BaseModel):
    product_name: str
    quantity: int


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(OrderItemBase):
    id: str
    unit_price: float
    total_price: float
    product: ProductResponse

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    delivery_address: str
    delivery_instructions: Optional[str] = None


class OrderCreate(OrderBase):
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    delivery_instructions: Optional[str] = None


class OrderResponse(OrderBase):
    id: str
    total_amount: float
    delivery_fee: float
    tax_amount: float
    final_amount: float
    status: OrderStatus
    created_at: str
    customer: UserResponse
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True


# Delivery Schemas
class DeliveryBase(BaseModel):
    order_id: str
    delivery_notes: Optional[str] = None


class DeliveryCreate(DeliveryBase):
    pass


class DeliveryUpdate(BaseModel):
    status: Optional[str] = None
    delivery_notes: Optional[str] = None
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None


class DeliveryResponse(DeliveryBase):
    id: str
    status: str
    assigned_at: str
    order: OrderResponse

    class Config:
        from_attributes = True


# Statistics Schemas
class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_customers: int
    pending_orders: int
    completed_deliveries: int
