from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Optional
from datetime import datetime

# Mock data
mock_categories = [
    {
        "id": "1",
        "name": "Bread",
        "description": "Fresh baked breads",
        "created_at": datetime.now().isoformat()
    },
    {
        "id": "2", 
        "name": "Cakes",
        "description": "Delicious cakes for all occasions",
        "created_at": datetime.now().isoformat()
    },
    {
        "id": "3",
        "name": "Pastries", 
        "description": "Sweet and savory pastries",
        "created_at": datetime.now().isoformat()
    },
    {
        "id": "4",
        "name": "Cookies",
        "description": "Homemade cookies", 
        "created_at": datetime.now().isoformat()
    }
]

mock_products = [
    {
        "id": "1",
        "name": "Ensaymada",
        "description": "Traditional Filipino sweet bread topped with cheese and sugar",
        "price": 45.00,
        "stock_quantity": 20,
        "is_available": True,
        "created_at": datetime.now().isoformat(),
        "category": mock_categories[0]
    },
    {
        "id": "2",
        "name": "Chocolate Cake",
        "description": "Rich chocolate cake with buttercream frosting",
        "price": 350.00,
        "stock_quantity": 5,
        "is_available": True,
        "created_at": datetime.now().isoformat(),
        "category": mock_categories[1]
    },
    {
        "id": "3",
        "name": "Ube Hopia",
        "description": "Purple yam filled pastry, a Filipino favorite",
        "price": 25.00,
        "stock_quantity": 30,
        "is_available": True,
        "created_at": datetime.now().isoformat(),
        "category": mock_categories[2]
    },
    {
        "id": "4",
        "name": "Pan de Sal",
        "description": "Classic Filipino bread roll",
        "price": 15.00,
        "stock_quantity": 50,
        "is_available": True,
        "created_at": datetime.now().isoformat(),
        "category": mock_categories[0]
    },
    {
        "id": "5",
        "name": "Cheese Roll",
        "description": "Soft bread roll filled with cheese",
        "price": 20.00,
        "stock_quantity": 0,
        "is_available": False,
        "created_at": datetime.now().isoformat(),
        "category": mock_categories[0]
    }
]

# FastAPI App
app = FastAPI(
    title="Bongao Bakery API (Mock)",
    description="Mock API for Bongao Bakery ordering and Delivery System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Bongao Bakery API (Mock Mode)", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "mock"}

# Categories endpoints
@app.get("/api/categories/")
async def get_categories():
    """Get all categories"""
    return mock_categories

@app.post("/api/categories/")
async def create_category(category_data: dict):
    """Create a new category"""
    new_category = {
        "id": str(len(mock_categories) + 1),
        "name": category_data.get("name"),
        "description": category_data.get("description"),
        "created_at": datetime.now().isoformat()
    }
    mock_categories.append(new_category)
    return new_category

# Products endpoints
@app.get("/api/products/")
async def get_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None
):
    """Get all products with optional filtering"""
    filtered_products = mock_products.copy()
    
    # Filter by category_id
    if category_id:
        filtered_products = [p for p in filtered_products if p["category"]["id"] == str(category_id)]
    
    # Filter by search
    if search:
        search_lower = search.lower()
        filtered_products = [p for p in filtered_products 
                           if search_lower in p["name"].lower() or 
                           search_lower in (p["description"] or "").lower()]
    
    # Filter by price range
    if min_price is not None:
        filtered_products = [p for p in filtered_products if p["price"] >= min_price]
    
    if max_price is not None:
        filtered_products = [p for p in filtered_products if p["price"] <= max_price]
    
    # Filter by stock availability
    if in_stock is True:
        filtered_products = [p for p in filtered_products if p["is_available"] and p["stock_quantity"] > 0]
    elif in_stock is False:
        filtered_products = [p for p in filtered_products if not p["is_available"] or p["stock_quantity"] == 0]
    else:
        # Default: only show available products
        filtered_products = [p for p in filtered_products if p["is_available"]]
    
    return filtered_products

@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    """Get a specific product by ID"""
    for product in mock_products:
        if product["id"] == product_id:
            return product
    return {"error": "Product not found"}

@app.post("/api/products/")
async def create_product(product_data: dict):
    """Create a new product"""
    # Find category by name
    category = None
    for cat in mock_categories:
        if cat["name"] == product_data.get("category_name"):
            category = cat
            break
    
    if not category:
        return {"error": "Category not found"}
    
    new_product = {
        "id": str(len(mock_products) + 1),
        "name": product_data.get("name"),
        "description": product_data.get("description"),
        "price": product_data.get("price"),
        "stock_quantity": product_data.get("stock_quantity", 0),
        "is_available": True,
        "created_at": datetime.now().isoformat(),
        "category": category
    }
    mock_products.append(new_product)
    return new_product

@app.put("/api/products/{product_id}")
async def update_product(product_id: str, product_data: dict):
    """Update a product"""
    for i, product in enumerate(mock_products):
        if product["id"] == product_id:
            # Update product fields
            for key, value in product_data.items():
                if key in product and value is not None:
                    product[key] = value
            
            # Handle category update
            if "category_name" in product_data:
                for cat in mock_categories:
                    if cat["name"] == product_data["category_name"]:
                        product["category"] = cat
                        break
            
            return product
    
    return {"error": "Product not found"}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str):
    """Soft delete a product"""
    for product in mock_products:
        if product["id"] == product_id:
            product["is_available"] = False
            return {"message": "Product deleted successfully", "deleted_product_id": product_id}
    
    return {"error": "Product not found"}

# Auth endpoints (mock)
@app.post("/api/auth/login-form")
async def login(credentials: dict):
    """Mock login endpoint"""
    return {
        "access_token": "mock_token_12345",
        "token_type": "bearer"
    }

@app.post("/api/auth/register")
async def register(user_data: dict):
    """Mock register endpoint"""
    return {
        "id": 1,
        "email": user_data.get("email"),
        "username": user_data.get("username"),
        "full_name": user_data.get("full_name"),
        "role": user_data.get("role", "customer"),
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }

@app.get("/api/auth/me")
async def get_current_user():
    """Mock get current user endpoint"""
    return {
        "id": 1,
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "role": "customer",
        "is_active": True
    }

# Orders endpoints (mock)
@app.get("/api/orders/")
async def get_orders():
    """Mock get orders endpoint"""
    return []

@app.get("/api/orders/admin/all")
async def get_all_orders():
    """Mock get all orders endpoint"""
    return []

@app.post("/api/orders/")
async def create_order(order_data: dict):
    """Mock create order endpoint"""
    return {
        "id": "1",
        "total_amount": 100.0,
        "delivery_fee": 10.0,
        "tax_amount": 12.0,
        "final_amount": 122.0,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "customer": {"id": 1, "email": "test@example.com"},
        "items": []
    }

# Users endpoints (mock)
@app.get("/api/users/")
async def get_users():
    """Mock get users endpoint"""
    return []

if __name__ == "__main__":
    print("Starting mock server on http://localhost:8001")
    uvicorn.run("mock_server:app", host="0.0.0.0", port=8001, reload=False)
