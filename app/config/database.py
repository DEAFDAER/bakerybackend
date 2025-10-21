import logging
from neo4j import GraphDatabase
from .settings import settings


class Neo4jConnection:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
                database=settings.neo4j_database,
                max_connection_lifetime=300,  # 5 minutes
                max_connection_pool_size=50,
                connection_timeout=5  # 5 seconds timeout
            )
            self.driver.verify_connectivity()
            print("✅ Successfully connected to Neo4j database.")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            raise e

    def close(self):
        self.driver.close()

    def get_session(self):
        return self.driver.session(database=settings.neo4j_database)


# Global database connection
db_connection = Neo4jConnection()


def get_db():
    """Get Neo4j database session"""
    try:
        session = db_connection.get_session()
        yield session
    finally:
        session.close()


def close_db():
    """Close database connection"""
    db_connection.close()


def init_db():
    """Initialize database with constraints and indexes"""
    with db_connection.get_session() as session:
        # Create constraints for unique fields
        constraints = [
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
            "CREATE CONSTRAINT user_username_unique IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE",
            "CREATE CONSTRAINT product_name_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception as e:
                if "equivalent" in str(e).lower() or "already exists" in str(e).lower():
                    continue  # Constraint already exists
                else:
                    print(f"Warning: Could not create constraint: {e}")


def seed_data():
    """Seed initial data for development"""
    with db_connection.get_session() as session:
        # Create sample categories
        categories = [
            {"name": "Bread", "description": "Fresh baked breads"},
            {"name": "Cakes", "description": "Delicious cakes for all occasions"},
            {"name": "Pastries", "description": "Sweet and savory pastries"},
            {"name": "Cookies", "description": "Homemade cookies"},
        ]

        for cat_data in categories:
            session.run("""
                MERGE (c:Category {name: $name})
                SET c.description = $description, c.created_at = datetime()
            """, **cat_data)

        # Create sample baker user
        baker_data = {
            "username": "baker1",
            "email": "baker@bongao-bakery.com",
            "full_name": "Master Baker",
            "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeehdBP6fEtTT2/Dm",  # "password"
            "role": "baker",
            "phone": "+63-917-123-4567",
            "address": "Bongao Main Street, Tawi-Tawi"
        }

        session.run("""
            MERGE (u:User {email: $email})
            SET u += $props, u.created_at = datetime(), u.is_active = true
        """, email=baker_data["email"], props=baker_data)


def get_database_info():
    """Get database information"""
    with db_connection.get_session() as session:
        result = session.run("CALL dbms.components() YIELD name, versions, edition")
        return [record.data() for record in result]
