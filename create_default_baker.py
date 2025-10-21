from neo4j import GraphDatabase
from passlib.hash import bcrypt
from app.config.settings import settings

# Hash the password
password = "baker123"
hashed_password = bcrypt.hash(password)

# Connect to database
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
    database=settings.neo4j_database
)

try:
    with driver.session() as session:
        # Create default baker user
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
            username="defaultbaker",
            email="default@baker.com",
            full_name="Default Baker",
            hashed_password=hashed_password,
            role="baker",
            phone="+63-900-000-0001",
            address="Bakery Address"
        )
        
        record = result.single()
        if record:
            print("✅ Default baker account created successfully!")
            print(f"Username: defaultbaker")
            print(f"Email: default@baker.com")
            print(f"Password: baker123")
            print(f"Role: baker")
        else:
            print("❌ Failed to create default baker account")
            
finally:
    driver.close()
