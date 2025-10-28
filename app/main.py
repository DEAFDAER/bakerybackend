from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config.settings import settings
from .config.database import init_db, seed_data
from .routers import auth, products, users, orders, deliveries

# Initialize database and seed data
try:
    init_db()
    seed_data()
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")
    print("The application will continue but some features may not work properly.")

app = FastAPI(
    title="Bongao Bakery API",
    description="API for Bongao Bakery ordering and Delivery System",
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware - Allow frontend URLs
# In production, set FRONTEND_URL environment variable
frontend_url = settings.frontend_url if hasattr(settings, 'frontend_url') else "http://localhost:3000"
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    frontend_url,
    "https://frontendbakery-1.onrender.com"  # Render frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth, prefix="/api/auth", tags=["Authentication"])
app.include_router(products, prefix="/api/products", tags=["Products"])
app.include_router(users, prefix="/api/users", tags=["Users"])
app.include_router(orders, prefix="/api/orders", tags=["Orders"])
app.include_router(deliveries, prefix="/api/deliveries", tags=["Deliveries"])

@app.get("/")
async def root():
    return {"message": "Welcome to Bongao Bakery API", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "neo4j"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )