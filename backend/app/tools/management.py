from app.core.context import current_db_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re

# --- SAFE WRITE TOOLS ---

async def create_blog_post(title: str, content: str, image_url: str = None) -> str:
    """
    Safely creates a new blog post.
    PREVENTS: SQL Injection, XSS (basic), and unvalidated inserts.
    """
    # 1. VALIDATION LAYER (The "Shield")
    if len(title) > 100:
        return "Error: Title is too long (max 100 chars)."
    
    # Basic Script Tag Removal (Sanitization)
    clean_content = re.sub(r'<script.*?>.*?</script>', '', content, flags=re.DOTALL)
    
    db_url = current_db_url.get()
    if not db_url:
        return "Error: No Client Connection."

    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # 2. PARAMETERIZED QUERY (The "Scalpel")
            # We do NOT inject strings. We use :params.
            query = text("""
                INSERT INTO blogs (title, content, image_url, created_at)
                VALUES (:title, :content, :image, NOW())
                RETURNING id
            """)
            
            # Note: This assumes the client HAS a table named 'blogs'.
            # In a real SaaS, we'd check the schema first or have a standardized schema.
            await session.execute(query, {"title": title, "content": clean_content, "image": image_url})
            await session.commit()
            
        await engine.dispose()
        
        success_msg = f"✅ Blog post '{title}' created successfully."
        if image_url:
            success_msg += f" Image: {image_url}"
        return success_msg

    except Exception as e:
        return f"Database Write Error: {e}"

async def update_user_bio(user_id: int, new_bio: str) -> str:
    """
    Safely updates a user's bio. 
    Restricted: Cannot change username, password, or role.
    """
    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            query = text("UPDATE users SET bio = :bio WHERE id = :uid")
            result = await session.execute(query, {"bio": new_bio, "uid": user_id})
            await session.commit()
            
            if result.rowcount == 0:
                return "Error: User not found."
                
        await engine.dispose()
        return "✅ User bio updated."
    except Exception as e:
        return f"Update Error: {e}"
