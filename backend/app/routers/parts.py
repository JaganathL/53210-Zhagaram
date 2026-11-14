from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..auth import require_admin
from ..bootstrap import image_id_from_url, new_id
from ..deps import get_store
from ..models import Part, PartCreate, PartUpdate
from ..storage import DuplicateSkuError, Store, now

router = APIRouter(prefix="/api", tags=["items"])


def _require_category(store: Store, name: str) -> str:
    category = store.find_category(name)
    if not category:
        raise HTTPException(422, f"Unknown category '{name}'")
    return category.name


def release_image(store: Store, url: str) -> None:
    """Delete a database image once no item references it."""
    image_id = image_id_from_url(url)
    if image_id and not store.image_url_in_use(url):
        store.delete_image(image_id)


@router.get("/parts", response_model=list[Part])
def list_parts(
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=40),
    sort: Literal["newest", "price_asc", "price_desc", "name"] = "newest",
    store: Store = Depends(get_store),
) -> list[Part]:
    parts = store.list_parts()
    if category:
        parts = [p for p in parts if p.category == category]
    if search:
        term = search.strip().lower()
        parts = [
            p
            for p in parts
            if term in p.name.lower()
            or term in p.brand.lower()
            or term in p.sku.lower()
            or term in p.category.lower()
        ]
    sorters = {
        "newest": (lambda p: p.created_at, True),
        "price_asc": (lambda p: p.price, False),
        "price_desc": (lambda p: p.price, True),
        "name": (lambda p: p.name.lower(), False),
    }
    key, reverse = sorters[sort]
    return sorted(parts, key=key, reverse=reverse)


@router.get("/parts/{part_id}", response_model=Part)
def get_part(part_id: str, store: Store = Depends(get_store)) -> Part:
    part = store.get_part(part_id)
    if not part:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return part


@router.post("/parts", response_model=Part, status_code=status.HTTP_201_CREATED)
def create_part(
    data: PartCreate,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> Part:
    category = _require_category(store, data.category)
    ts = now()
    part = Part(
        id=new_id(), createdAt=ts, updatedAt=ts,
        **data.model_dump(by_alias=True, exclude={"category"}), category=category,
    )
    try:
        store.insert_part(part)
    except DuplicateSkuError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return part


@router.put("/parts/{part_id}", response_model=Part)
def update_part(
    part_id: str,
    data: PartUpdate,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> Part:
    existing = store.get_part(part_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    category = _require_category(store, data.category)
    part = Part(
        id=existing.id, createdAt=existing.created_at, updatedAt=now(),
        **data.model_dump(by_alias=True, exclude={"category"}), category=category,
    )
    try:
        if not store.replace_part(part):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    except DuplicateSkuError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if existing.image_url != part.image_url:
        release_image(store, existing.image_url)
    return part


@router.delete("/parts/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part(
    part_id: str,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> Response:
    existing = store.get_part(part_id)
    if not existing or not store.delete_part(part_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    release_image(store, existing.image_url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
