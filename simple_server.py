from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from neo4j import GraphDatabase
from app.config.settings import settings

# --- Database Connection ---
class Neo4jConnection:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
                database=settings.neo4j_database
            )
            self.driver.verify_connectivity()
            print("✅ Successfully connected to Neo4j database.")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            raise e

    def get_session(self):
        return self.driver.session(database=settings.neo4j_database)

db_connection = Neo4jConnection()

def get_db():
    try:
        session = db_connection.get_session()
        yield session
    finally:
        if session:
            session.close()

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/products/")
async def get_products_simple():
    print("GET /api/products/ called. Returning empty list.")
    return []

@app.get("/api/categories/")
async def get_categories_simple():
    print("GET /api/categories/ called. Returning empty list.")
    return []

@app.get("/api/orders/admin/all")
async def get_all_orders_simple():
    print("GET /api/orders/admin/all called. Returning empty list.")
    return []

@app.get("/api/users/")
async def get_users_simple(db=Depends(get_db)):
    print("GET /api/users/ called. Fetching users from database.")
    try:
        result = db.run("""
            MATCH (u:User)
            RETURN u
        """)
        
        users = []
        for record in result:
            user_node = record["u"]
            users.append({
                "id": str(user_node.id),
                "email": user_node.get("email"),
                "username": user_node.get("username"),
                "full_name": user_node.get("full_name"),
                "phone": user_node.get("phone"),
                "address": user_node.get("address"),
                "role": user_node.get("role"),
                "is_active": user_node.get("is_active", True),
                "created_at": str(user_node.get("created_at"))
            })
        
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []

@app.post("/api/products/")
async def create_product_simple(product_data: dict, db=Depends(get_db)):
    print(f"Received product data: {product_data}")
    try:
        result = db.run("""
            MATCH (c:Category {name: $category_name})
            MATCH (b:User {email: $baker_email})
            CREATE (p:Product {
                name: $name,
                description: $description,
                price: $price,
                stock_quantity: $stock_quantity,
                is_available: true,
                created_at: datetime()
            })
            CREATE (p)-[:BELONGS_TO]->(c)
            CREATE (b)-[:BAKES]->(p)
            RETURN p, c, b
        """, **product_data)

        record = result.single()
        if not record:
            return {"status": "error", "message": "Failed to create product"}

        product_node = record["p"]
        return {"status": "success", "id": product_node.id}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {"message": "Simple server is running"}

if __name__ == "__main__":
    print("Starting simple server on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
