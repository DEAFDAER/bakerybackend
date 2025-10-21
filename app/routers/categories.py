from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from ..config.database import get_db
from ..models.schemas import CategoryCreate, CategoryResponse

router = APIRouter()


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db=Depends(get_db)):
    """Get all categories"""
    try:
        result = db.run("MATCH (c:Category) RETURN c, elementId(c) as id")
        categories = []
        for record in result:
            cat_data = record["c"]
            categories.append(CategoryResponse(
                id=record["id"],
                name=cat_data["name"],
                description=cat_data.get("description"),
                created_at=str(cat_data["created_at"])
            ))
        return categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=CategoryResponse)
async def create_category(category: CategoryCreate, db=Depends(get_db)):
    """Create a new category"""
    try:
        result = db.run("""
            CREATE (c:Category {
                name: $name,
                description: $description,
                created_at: datetime()
            })
            RETURN c
        """, **category.dict())

        record = result.single()
        if not record:
            raise HTTPException(status_code=500, detail="Failed to create category")

        cat_data = record["c"]
        return CategoryResponse(
            id=str(cat_data.id),
            name=cat_data["name"],
            description=cat_data.get("description"),
            created_at=str(cat_data["created_at"])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: str, db=Depends(get_db)):
    """Get category by ID"""
    try:
        result = db.run("""
            MATCH (c:Category)
            WHERE elementId(c) = $category_id
            RETURN c
        """, category_id=category_id)

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Category not found")

        cat_data = record["c"]
        return CategoryResponse(
            id=str(cat_data.id),
            name=cat_data["name"],
            description=cat_data.get("description"),
            created_at=str(cat_data["created_at"])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, category_update: CategoryCreate, db=Depends(get_db)):
    """Update category"""
    try:
        update_props = category_update.dict(exclude_unset=True)
        set_clause = ", ".join([f"c.{k} = ${k}" for k in update_props.keys()])

        result = db.run(f"""
            MATCH (c:Category)
            WHERE elementId(c) = $category_id
            SET {set_clause}, c.updated_at = datetime()
            RETURN c
        """, category_id=category_id, **update_props)

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Category not found")

        cat_data = record["c"]
        return CategoryResponse(
            id=str(cat_data.id),
            name=cat_data["name"],
            description=cat_data.get("description"),
            created_at=str(cat_data["created_at"])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{category_id}")
async def delete_category(category_id: str, db=Depends(get_db)):
    """Delete category"""
    try:
        result = db.run("""
            MATCH (c:Category)
            WHERE elementId(c) = $category_id
            DETACH DELETE c
        """, category_id=category_id)

        if result.consume().counters.nodes_deleted == 0:
            raise HTTPException(status_code=404, detail="Category not found")

        return {"message": "Category deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
