from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlmodel import select, delete
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.schema_metadata import SchemaMetadata
from app.models.client_config import ClientConfig
from pydantic import BaseModel
import os

router = APIRouter()

class SchemaItem(BaseModel):
    table_name: str
    schema_definition: str

@router.post("/schema/learn")
async def learn_schema(
    items: List[SchemaItem],
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    # 1. Auth check
    stmt = select(ClientConfig).where(ClientConfig.api_key == api_key)
    res = await session.execute(stmt)
    client = res.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. Clear old schema for this client
    await session.execute(delete(SchemaMetadata).where(SchemaMetadata.client_id == client.id))
    
    # 3. Vectorize and save
    new_schemas = []
    
    # Setup embedder
    embedder = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        except Exception as e:
            print(f"Warning: Failed to load embedder: {e}")
            
    for item in items:
        new_obj = SchemaMetadata(
            client_id=client.id,
            table_name=item.table_name,
            schema_definition=item.schema_definition
        )
        
        # Generate Vector embedding if API key is set
        if embedder:
            try:
                vec = await embedder.aembed_query(item.schema_definition)
                new_obj.embedding = vec
            except Exception as e:
                print(f"Failed to embed schema for {item.table_name}: {e}")
                
        new_schemas.append(new_obj)
        session.add(new_obj)
        
    client.schema_synced = True
    session.add(client)
    
    await session.commit()
    
    return {"status": "success", "tables_learned": len(new_schemas)}
