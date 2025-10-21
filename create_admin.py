from neo4j import GraphDatabase
from passlib.hash import bcrypt
from app.config.settings import settings

# Hash the password
password = "12345678"
hashed_password = bcrypt.hash(password)

# Connect to database
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
    database=settings.neo4j_database
)

try:
    with driver.session() as session:
        # Create admin user
        result = session.run("""
            MERGE (u:User {username: $username})
            SET u.email = $email,
                u.full_name = $full_name,
                u.hashed_password = $hashed_password,
                u.role = $role,
                u.is_active = true,
                u.created_at = datetime(),
                u.phone = $phone,
                u.address = $address
            RETURN u
        """, 
            username="gab1",
            email="gab1@admin.com",
            full_name="Gab Admin",
            hashed_password=hashed_password,
            role="admin",
            phone="+63-900-000-0000",
            address="Admin Office"
        )
        
        record = result.single()
        if record:
            print("✅ Admin account created successfully!")
            print(f"Username: gab1")
            print(f"Email: gab1@admin.com")
            print(f"Password: 12345678")
            print(f"Role: admin")
        else:
            print("❌ Failed to create admin account")
            
finally:
    driver.close()
