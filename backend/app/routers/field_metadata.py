from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List
from app.core.database import get_session
from app.models.field_metadata import FieldMetadata
from app.core.auth_deps import get_current_active_admin
from pydantic import BaseModel
from sqlalchemy import text, create_engine
from app.models.client_config import ClientConfig

router = APIRouter(prefix="/field-metadata", dependencies=[Depends(get_current_active_admin)])

class FieldMetadataUpdate(BaseModel):
    label: str
    input_type: str
    storage_type: str = "string"
    data_source_table: str = None
    value_column: str = None
    display_column: str = None
    required: bool = False
    readonly: bool = False
    is_visible: bool = True
    default_value: str = None

class FieldMetadataCreate(FieldMetadataUpdate):
    client_id: int
    table_name: str
    column_name: str

@router.post("/", response_model=FieldMetadata)
@router.post("", response_model=FieldMetadata)
async def create_field_metadata(
    payload: FieldMetadataCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Manually create a metadata record if one doesn't exist.
    """
    stmt = select(FieldMetadata).where(
        FieldMetadata.client_id == payload.client_id,
        FieldMetadata.table_name == payload.table_name,
        FieldMetadata.column_name == payload.column_name
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        update_data = payload.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing, key, value)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    new_meta = FieldMetadata(**payload.dict())
    session.add(new_meta)
    await session.commit()
    await session.refresh(new_meta)
    return new_meta

@router.get("/sample/{client_id}/{table_name}")
async def get_table_sample_data(
    client_id: int,
    table_name: str,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    try:
        engine = create_engine(client.db_connection_url)
        with engine.connect() as conn:
            query = text(f"SELECT * FROM {table_name} LIMIT 1")
            result = conn.execute(query).mappings().first()
            return dict(result) if result else {}
    except Exception as e:
        return {}

@router.get("/{client_id}/{table_name}", response_model=List[FieldMetadata])
async def get_table_field_metadata(
    client_id: int,
    table_name: str,
    session: AsyncSession = Depends(get_session)
):
    stmt = select(FieldMetadata).where(
        FieldMetadata.client_id == client_id,
        FieldMetadata.table_name == table_name
    ).order_by(FieldMetadata.column_name)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.put("/{metadata_id}", response_model=FieldMetadata)
async def update_field_metadata(
    metadata_id: int,
    payload: FieldMetadataUpdate,
    session: AsyncSession = Depends(get_session)
):
    meta = await session.get(FieldMetadata, metadata_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Metadata not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(meta, key, value)
    session.add(meta)
    await session.commit()
    await session.refresh(meta)
    return meta
