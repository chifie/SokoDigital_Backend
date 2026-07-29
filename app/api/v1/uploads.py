import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user
from app.config import settings
from app.middleware.rate_limit import UPLOAD_RATE_LIMIT, rate_limit
from app.models.user import User

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# Allowed file types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
}

MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE


def _ensure_upload_dir(subdir: str = "") -> Path:
    """Ensure the upload directory exists and return its path."""
    upload_base = Path(settings.UPLOAD_DIR)
    target = upload_base / subdir if subdir else upload_base
    target.mkdir(parents=True, exist_ok=True)
    return target


@router.post(
    "/image",
    summary="Upload an image file",
    response_description="URL and metadata of the uploaded image",
    responses={
        400: {"description": "Unsupported image type"},
        413: {"description": "File too large"},
    },
)
async def upload_image(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit(UPLOAD_RATE_LIMIT)),
):
    """Upload an image file (JPEG, PNG, GIF, WebP, SVG).

    Returns the URL path to the uploaded file.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {file.content_type}. "
                   f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    return await _save_upload(file, "images")


@router.post(
    "/document",
    summary="Upload a document file",
    response_description="URL and metadata of the uploaded document",
    responses={
        400: {"description": "Unsupported document type"},
        413: {"description": "File too large"},
    },
)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit(UPLOAD_RATE_LIMIT)),
):
    """Upload a document file (PDF, TXT, CSV).

    Returns the URL path to the uploaded file.
    """
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported document type: {file.content_type}. "
                   f"Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_TYPES))}",
        )

    return await _save_upload(file, "documents")


@router.post(
    "/any",
    summary="Upload an image or document file",
    response_description="URL and metadata of the uploaded file",
    responses={
        400: {"description": "Unsupported file type"},
        413: {"description": "File too large"},
    },
)
async def upload_any(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit(UPLOAD_RATE_LIMIT)),
):
    """Upload an image or document file.

    Returns the URL path to the uploaded file.
    """
    allowed = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    subdir = "images" if file.content_type in ALLOWED_IMAGE_TYPES else "documents"
    return await _save_upload(file, subdir)


async def _save_upload(file: UploadFile, subdir: str) -> dict:
    """Save an uploaded file to disk and return its path info."""
    # Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Generate a unique filename
    ext = os.path.splitext(file.filename or "file")[1] or ""
    unique_name = f"{uuid.uuid4().hex}{ext}"

    # Save to disk
    target_dir = _ensure_upload_dir(subdir)
    file_path = target_dir / unique_name
    with open(file_path, "wb") as f:
        f.write(contents)

    # Return the URL path (relative to the server root)
    url_path = f"/uploads/{subdir}/{unique_name}"
    return {
        "url": url_path,
        "filename": unique_name,
        "original_name": file.filename,
        "size": len(contents),
        "content_type": file.content_type,
    }
