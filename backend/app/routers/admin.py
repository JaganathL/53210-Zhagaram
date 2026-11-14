import mimetypes
import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from ..auth import create_token, require_admin, verify_credentials
from ..bootstrap import image_url, new_id
from ..config import Settings, get_settings
from ..deps import get_store
from ..models import ImageRecord, LoginRequest, TokenResponse, UploadResponse
from ..storage import Store, now

router = APIRouter(prefix="/api", tags=["admin", "images"])

# SVG is intentionally excluded from uploads: uploaded SVGs can carry scripts.
_ALLOWED = {
    "image/jpeg": (".jpg", [b"\xff\xd8\xff"]),
    "image/png": (".png", [b"\x89PNG\r\n\x1a\n"]),
    "image/webp": (".webp", [b"RIFF"]),
}
_IMAGE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
}


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    if not verify_credentials(body.username, body.password, settings):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    return TokenResponse(
        access_token=create_token(settings), expires_in=settings.jwt_expire_minutes * 60
    )


@router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> UploadResponse:
    allowed = _ALLOWED.get(file.content_type or "")
    if not allowed:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPG, PNG or WEBP images are allowed")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image must be 2 MB or smaller")
    ext, magics = allowed
    if not any(content.startswith(m) for m in magics) or (ext == ".webp" and content[8:12] != b"WEBP"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File content is not a valid image")
    record = ImageRecord(new_id(), file.content_type, f"upload{ext}", content, now())
    store.insert_image(record)
    return UploadResponse(image_url=image_url(record.id))


def _load(store: Store, image_id: str) -> ImageRecord:
    record = store.get_image(image_id) if re.fullmatch(r"[0-9a-f]{32}", image_id) else None
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    return record


@router.get("/images/{image_id}")
def get_image(image_id: str, store: Store = Depends(get_store)) -> Response:
    record = _load(store, image_id)
    return Response(record.data, media_type=record.content_type, headers=_IMAGE_HEADERS)


@router.get("/images/{image_id}/download")
def download_image(
    image_id: str,
    filename: str = Query(default="", max_length=120),
    store: Store = Depends(get_store),
) -> Response:
    record = _load(store, image_id)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", filename).strip("-")[:80] or "zhagaram-jewellery"
    ext = mimetypes.guess_extension(record.content_type) or ""
    headers = {**_IMAGE_HEADERS, "Content-Disposition": f'attachment; filename="{stem}{ext}"'}
    return Response(record.data, media_type=record.content_type, headers=headers)
