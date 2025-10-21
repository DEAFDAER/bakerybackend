from neo4j import GraphDatabase
from app.config.settings import settings

# Connect to database
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
    database=settings.neo4j_database
)

try:
    with driver.session() as session:
        # Delete all products and their relationships
        result = session.run("""
            MATCH (p:Product)
            DETACH DELETE p
            RETURN count(p) as deleted_count
        """)
        
        record = result.single()
        deleted_count = record["deleted_count"] if record else 0
        
        print(f"✅ Deleted {deleted_count} products from the database")
        print("All example/test products have been removed.")
            
finally:
    driver.close()
