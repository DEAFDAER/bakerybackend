from neo4j import GraphDatabase
from passlib.hash import bcrypt
from app.config.settings import settings

# Hash the password
password = "customer123"
hashed_password = bcrypt.hash(password)

# Connect to database
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
    database=settings.neo4j_database
)

try:
    with driver.session() as session:
        # Create customer user
        result = session.run("""
            MERGE (u:User {email: $email})
            SET u.username = $username,
                u.full_name = $full_name,
                u.hashed_password = $hashed_password,
                u.role = $role,
                u.is_active = true,
                u.created_at = datetime(),
                u.phone = $phone,
                u.address = $address
            RETURN u
        """, 
            username="customer1",
            email="customer@example.com",
            full_name="Test Customer",
            hashed_password=hashed_password,
            role="customer",
            phone="+63-900-000-0002",
            address="Customer Address, Bongao"
        )
        
        record = result.single()
        if record:
            print("✅ Customer account created successfully!")
            print(f"Username: customer1")
            print(f"Email: customer@example.com")
            print(f"Password: customer123")
            print(f"Role: customer")
        else:
            print("❌ Failed to create customer account")
            
finally:
    driver.close()
