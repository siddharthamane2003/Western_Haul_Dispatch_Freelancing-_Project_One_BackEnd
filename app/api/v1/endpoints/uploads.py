import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image
from io import BytesIO

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, DocumentType
from app.repositories.repositories import DocumentRepository
from app.core.config import settings

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/jpg",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


async def compress_image(file_bytes: bytes, max_size: tuple = (1920, 1080), quality: int = 85) -> bytes:
    """Compress image while maintaining quality."""
    try:
        image = Image.open(BytesIO(file_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception:
        return file_bytes


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.OTHER,
    order_id: Optional[uuid.UUID] = None,
    driver_id: Optional[uuid.UUID] = None,
    vehicle_id: Optional[uuid.UUID] = None,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document or image."""
    # Validate content type
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file.content_type}")

    # Validate file size
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

    # Compress images
    if file.content_type in ("image/jpeg", "image/png", "image/jpg"):
        file_bytes = await compress_image(file_bytes)
        ext = ".jpg"
    else:
        ext = Path(file.filename).suffix if file.filename else ".bin"

    # Generate unique filename
    file_id = uuid.uuid4()
    filename = f"{file_id}{ext}"

    # Determine directory
    subdir = str(document_type.value)
    save_dir = UPLOAD_DIR / subdir
    save_dir.mkdir(exist_ok=True)
    file_path = save_dir / filename

    # Save file
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    # Save to database
    repo = DocumentRepository(db)
    doc = await repo.create({
        "order_id": order_id,
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "uploaded_by": current_user.id,
        "document_type": document_type,
        "file_name": file.filename or filename,
        "file_url": f"/uploads/{subdir}/{filename}",
        "file_size": len(file_bytes),
        "mime_type": file.content_type,
        "description": description,
    })

    return {
        "id": str(doc.id),
        "file_name": doc.file_name,
        "file_url": doc.file_url,
        "file_size": doc.file_size,
        "document_type": str(doc.document_type),
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/order/{order_id}")
async def get_order_documents(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all documents for an order."""
    repo = DocumentRepository(db)
    docs = await repo.get_by_order(order_id)
    return [
        {
            "id": str(d.id),
            "file_name": d.file_name,
            "file_url": d.file_url,
            "document_type": str(d.document_type),
            "description": d.description,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/driver/{driver_id}")
async def get_driver_documents(
    driver_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all documents for a driver."""
    repo = DocumentRepository(db)
    docs = await repo.get_by_driver(driver_id)
    return [
        {
            "id": str(d.id),
            "file_name": d.file_name,
            "file_url": d.file_url,
            "document_type": str(d.document_type),
            "description": d.description,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete / deactivate a document."""
    repo = DocumentRepository(db)
    doc = await repo.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await repo.update(document_id, {"is_active": False})
    return {"message": "Document deleted"}
