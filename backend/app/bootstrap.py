"""First-start population of an empty store: legacy migration or seed data."""

import json
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from .config import Settings
from .models import Category, ImageRecord, Part
from .seed import SEED_CATEGORIES, SEED_PARTS
from .storage import Store, now

log = logging.getLogger(__name__)

SEED_IMAGE_DIR = Path(__file__).resolve().parent / "seed_images"
IMAGE_URL_PREFIX = "/api/images/"
_LEGACY_FIELDS = {"stock", "compatibleVehicles"}


def image_url(image_id: str) -> str:
    return f"{IMAGE_URL_PREFIX}{image_id}"


def image_id_from_url(url: str) -> str | None:
    return url[len(IMAGE_URL_PREFIX):] if url.startswith(IMAGE_URL_PREFIX) else None


def new_id() -> str:
    return uuid.uuid4().hex


class _ImageLoader:
    """Stores each source file once and returns its database URL."""

    def __init__(self, store: Store):
        self._store = store
        self._cache: dict[Path, str] = {}

    def load(self, path: Path | None) -> str:
        if path is None or not path.is_file():
            return ""
        if path not in self._cache:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            record = ImageRecord(new_id(), content_type, path.name, path.read_bytes(), now())
            self._store.insert_image(record)
            self._cache[path] = image_url(record.id)
        return self._cache[path]


def _legacy_image_path(url: str, settings: Settings) -> Path | None:
    name = url.rsplit("/", 1)[-1]
    if url.startswith(("/static/items/", "/static/parts/")):
        return SEED_IMAGE_DIR / name
    if url.startswith("/uploads/"):
        return settings.legacy_upload_dir / name
    return None


def bootstrap(store: Store, settings: Settings) -> None:
    if not store.is_empty():
        return

    legacy_file = settings.legacy_data_file
    legacy = legacy_file.is_file()
    rows: list[dict[str, Any]] = (
        json.loads(legacy_file.read_text(encoding="utf-8")) if legacy else [dict(p) for p in SEED_PARTS]
    )

    category_names = [name for name, _ in SEED_CATEGORIES]
    rental = {name for name, is_rental in SEED_CATEGORIES if is_rental}
    for row in rows:
        if row["category"] not in category_names:
            category_names.append(row["category"])

    created = now()
    for order, name in enumerate(category_names):
        store.insert_category(
            Category(id=new_id(), name=name, rental=name in rental, order=order, createdAt=created)
        )

    images = _ImageLoader(store)
    for row in rows:
        for field in _LEGACY_FIELDS:
            row.pop(field, None)
        if "image" in row:
            row["imageUrl"] = images.load(SEED_IMAGE_DIR / row.pop("image"))
        else:
            row["imageUrl"] = images.load(_legacy_image_path(row.get("imageUrl", ""), settings))
        row.setdefault("id", new_id())
        row.setdefault("createdAt", created)
        row.setdefault("updatedAt", created)
        store.insert_part(Part.model_validate(row))

    if legacy:
        legacy_file.replace(legacy_file.with_suffix(".legacy.json"))
        log.info("Migrated %d items from %s", len(rows), legacy_file.name)
    else:
        log.info("Seeded %d items and %d categories", len(rows), len(category_names))
