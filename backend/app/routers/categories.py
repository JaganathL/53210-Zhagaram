from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..auth import require_admin
from ..bootstrap import new_id
from ..deps import get_store
from ..models import Category, CategoryIn, CategoryOut
from ..storage import DuplicateCategoryError, Store, now

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _out(category: Category, count: int) -> CategoryOut:
    return CategoryOut(**category.model_dump(by_alias=True), itemCount=count)


@router.get("", response_model=list[CategoryOut], response_model_by_alias=True)
def list_categories(store: Store = Depends(get_store)) -> list[CategoryOut]:
    counts = Counter(p.category for p in store.list_parts())
    return [_out(c, counts[c.name]) for c in store.list_categories()]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryIn,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> CategoryOut:
    existing = store.list_categories()
    category = Category(
        id=new_id(),
        name=data.name.strip(),
        rental=data.rental,
        order=max((c.order for c in existing), default=-1) + 1,
        createdAt=now(),
    )
    try:
        store.insert_category(category)
    except DuplicateCategoryError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return _out(category, 0)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    data: CategoryIn,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> CategoryOut:
    existing = store.get_category(category_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    updated = existing.model_copy(update={"name": data.name.strip(), "rental": data.rental})
    try:
        store.replace_category(updated)
    except DuplicateCategoryError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if updated.name != existing.name:
        store.rename_category_in_parts(existing.name, updated.name)
    return _out(updated, store.count_parts(updated.name))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: str,
    store: Store = Depends(get_store),
    _: str = Depends(require_admin),
) -> Response:
    existing = store.get_category(category_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    in_use = store.count_parts(existing.name)
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"'{existing.name}' has {in_use} item(s). Move or delete them first.",
        )
    store.delete_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
