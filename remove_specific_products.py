from neo4j import GraphDatabase
from app.config.settings import settings

# Connect to database
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
    database=settings.neo4j_database
)

products_to_remove = ["Chocolate Cake", "Ensaymada", "Ube Hopia"]

try:
    with driver.session() as session:
        for product_name in products_to_remove:
            # Delete specific product and its relationships
            result = session.run("""
                MATCH (p:Product {name: $product_name})
                DETACH DELETE p
                RETURN count(p) as deleted_count
            """, product_name=product_name)
            
            record = result.single()
            deleted_count = record["deleted_count"] if record else 0
            
            if deleted_count > 0:
                print(f"✅ Deleted '{product_name}'")
            else:
                print(f"⚠️  '{product_name}' not found")
        
        print("\nAll specified products have been removed.")
            
finally:
    driver.close()
