"""Storage backends.

`MongoStore` keeps categories, items and images (as binary) in MongoDB.
`JsonStore` mirrors the same documents in local JSON files and is used until a
MongoDB connection string is configured. Both expose the same methods so the
API layer is backend-agnostic.
"""

import base64
import json
import os
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from bson import ObjectId

from .models import Category, ImageRecord, Part


class DuplicateSkuError(ValueError):
    pass


class DuplicateCategoryError(ValueError):
    pass


class Store(Protocol):
    def is_empty(self) -> bool: ...

    def list_categories(self) -> list[Category]: ...
    def get_category(self, category_id: str) -> Category | None: ...
    def find_category(self, name: str) -> Category | None: ...
    def insert_category(self, category: Category) -> None: ...
    def replace_category(self, category: Category) -> bool: ...
    def delete_category(self, category_id: str) -> bool: ...

    def list_parts(self) -> list[Part]: ...
    def get_part(self, part_id: str) -> Part | None: ...
    def insert_part(self, part: Part) -> None: ...
    def replace_part(self, part: Part) -> bool: ...
    def delete_part(self, part_id: str) -> bool: ...
    def count_parts(self, category: str) -> int: ...
    def rename_category_in_parts(self, old: str, new: str) -> int: ...
    def image_url_in_use(self, url: str, exclude_part_id: str | None = None) -> bool: ...

    def insert_image(self, image: ImageRecord) -> None: ...
    def get_image(self, image_id: str) -> ImageRecord | None: ...
    def delete_image(self, image_id: str) -> bool: ...


# Document mapping shared by MongoDB and the JSON export/import tooling.

def category_to_doc(c: Category) -> dict[str, Any]:
    return {
        "_id": c.id,
        "name": c.name,
        "nameKey": c.name.casefold(),
        "rental": c.rental,
        "order": c.order,
        "createdAt": c.created_at,
    }


def doc_to_category(d: dict[str, Any]) -> Category:
    return Category(
        id=str(d["_id"]), name=d["name"], rental=d.get("rental", False), order=d.get("order", 0),
        createdAt=d["createdAt"],
    )


def part_to_doc(p: Part) -> dict[str, Any]:
    doc = p.model_dump(by_alias=True, exclude={"id"})
    return {"_id": p.id, "skuKey": p.sku.casefold(), **doc}


def doc_to_part(d: dict[str, Any]) -> Part:
    data = {k: v for k, v in d.items() if k not in ("_id", "skuKey")}
    return Part(id=d["_id"], **data)


def image_to_doc(i: ImageRecord) -> dict[str, Any]:
    return {
        "_id": i.id,
        "contentType": i.content_type,
        "filename": i.filename,
        "size": len(i.data),
        "data": i.data,
        "createdAt": i.created_at,
    }


def doc_to_image(d: dict[str, Any]) -> ImageRecord:
    return ImageRecord(
        id=d["_id"], content_type=d["contentType"], filename=d.get("filename", ""),
        data=bytes(d["data"]), created_at=d["createdAt"],
    )


class JsonStore:
    """Single-process JSON file store (one file per collection, atomic writes)."""

    def __init__(self, data_dir: Path):
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._categories: list[Category] = [
            Category.model_validate(c) for c in self._load("categories")
        ]
        self._parts: list[Part] = [Part.model_validate(p) for p in self._load("items")]
        self._images: dict[str, dict[str, Any]] = {i["id"]: i for i in self._load("images")}

    def _load(self, name: str) -> list[dict[str, Any]]:
        path = self._dir / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8") or "[]") if path.exists() else []

    def _save(self, name: str, rows: list[Any]) -> None:
        payload = json.dumps(rows, indent=2, ensure_ascii=False, default=str)
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        target = self._dir / f"{name}.json"
        # Windows can briefly lock the target (antivirus, indexer); retry the atomic swap.
        for attempt in range(10):
            try:
                os.replace(tmp, target)
                return
            except PermissionError:
                if attempt == 9:
                    os.unlink(tmp)
                    raise
                time.sleep(0.05 * (attempt + 1))

    def _save_categories(self) -> None:
        self._save("categories", [c.model_dump(mode="json", by_alias=True) for c in self._categories])

    def _save_parts(self) -> None:
        self._save("items", [p.model_dump(mode="json", by_alias=True) for p in self._parts])

    def _save_images(self) -> None:
        self._save("images", list(self._images.values()))

    def is_empty(self) -> bool:
        with self._lock:
            return not self._categories and not self._parts

    # Categories
    def list_categories(self) -> list[Category]:
        with self._lock:
            return sorted(self._categories, key=lambda c: c.order)

    def get_category(self, category_id: str) -> Category | None:
        with self._lock:
            return next((c for c in self._categories if c.id == category_id), None)

    def find_category(self, name: str) -> Category | None:
        key = name.casefold()
        with self._lock:
            return next((c for c in self._categories if c.name.casefold() == key), None)

    def _check_category_name(self, category: Category) -> None:
        existing = self.find_category(category.name)
        if existing and existing.id != category.id:
            raise DuplicateCategoryError(f"Category '{category.name}' already exists")

    def insert_category(self, category: Category) -> None:
        with self._lock:
            self._check_category_name(category)
            self._categories.append(category)
            self._save_categories()

    def replace_category(self, category: Category) -> bool:
        with self._lock:
            for i, c in enumerate(self._categories):
                if c.id == category.id:
                    self._check_category_name(category)
                    self._categories[i] = category
                    self._save_categories()
                    return True
            return False

    def delete_category(self, category_id: str) -> bool:
        with self._lock:
            before = len(self._categories)
            self._categories = [c for c in self._categories if c.id != category_id]
            if len(self._categories) == before:
                return False
            self._save_categories()
            return True

    # Items
    def list_parts(self) -> list[Part]:
        with self._lock:
            return list(self._parts)

    def get_part(self, part_id: str) -> Part | None:
        with self._lock:
            return next((p for p in self._parts if p.id == part_id), None)

    def _check_sku(self, part: Part) -> None:
        key = part.sku.casefold()
        if any(p.sku.casefold() == key and p.id != part.id for p in self._parts):
            raise DuplicateSkuError(f"SKU '{part.sku}' already exists")

    def insert_part(self, part: Part) -> None:
        with self._lock:
            self._check_sku(part)
            self._parts.append(part)
            self._save_parts()

    def replace_part(self, part: Part) -> bool:
        with self._lock:
            for i, p in enumerate(self._parts):
                if p.id == part.id:
                    self._check_sku(part)
                    self._parts[i] = part
                    self._save_parts()
                    return True
            return False

    def delete_part(self, part_id: str) -> bool:
        with self._lock:
            before = len(self._parts)
            self._parts = [p for p in self._parts if p.id != part_id]
            if len(self._parts) == before:
                return False
            self._save_parts()
            return True

    def count_parts(self, category: str) -> int:
        with self._lock:
            return sum(1 for p in self._parts if p.category == category)

    def rename_category_in_parts(self, old: str, new: str) -> int:
        with self._lock:
            changed = 0
            for i, p in enumerate(self._parts):
                if p.category == old:
                    self._parts[i] = p.model_copy(update={"category": new})
                    changed += 1
            if changed:
                self._save_parts()
            return changed

    def image_url_in_use(self, url: str, exclude_part_id: str | None = None) -> bool:
        with self._lock:
            return any(p.image_url == url and p.id != exclude_part_id for p in self._parts)

    # Images (base64 inside images.json)
    def insert_image(self, image: ImageRecord) -> None:
        with self._lock:
            self._images[image.id] = {
                "id": image.id,
                "contentType": image.content_type,
                "filename": image.filename,
                "createdAt": image.created_at.isoformat(),
                "data": base64.b64encode(image.data).decode("ascii"),
            }
            self._save_images()

    def get_image(self, image_id: str) -> ImageRecord | None:
        with self._lock:
            row = self._images.get(image_id)
        if not row:
            return None
        return ImageRecord(
            id=row["id"], content_type=row["contentType"], filename=row.get("filename", ""),
            data=base64.b64decode(row["data"]), created_at=datetime.fromisoformat(row["createdAt"]),
        )

    def delete_image(self, image_id: str) -> bool:
        with self._lock:
            if self._images.pop(image_id, None) is None:
                return False
            self._save_images()
            return True


class MongoStore:
    """MongoDB store. Collections: categories, items, images (binary data)."""

    def __init__(self, db: Any):
        self.categories = db["categories"]
        self.items = db["items"]
        self.images = db["images"]
        self.categories.create_index("nameKey", unique=True)
        self.categories.create_index("order")
        self.items.create_index("skuKey", unique=True)
        self.items.create_index("category")

    @classmethod
    def connect(cls, uri: str, db_name: str) -> "MongoStore":
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        client.admin.command("ping")
        db = client[db_name]
        cls._normalize_legacy_categories(db["categories"])
        store = cls(db)
        store._migrate_legacy_products(db["products"])
        return store

    @staticmethod
    def _normalize_legacy_categories(categories: Any) -> None:
        for order, category in enumerate(categories.find({}).sort("createdAt", 1)):
            updates: dict[str, Any] = {}
            if not category.get("nameKey"):
                updates["nameKey"] = category["name"].casefold()
            if "rental" not in category:
                updates["rental"] = bool(category.get("isRental", False))
            if "order" not in category:
                updates["order"] = order
            if updates:
                categories.update_one({"_id": category["_id"]}, {"$set": updates})

    def _migrate_legacy_products(self, products: Any) -> None:
        for product in products.find({}):
            part_id = str(product["_id"])
            if self.items.find_one({"_id": part_id}):
                continue

            category = self.categories.find_one({"_id": product.get("category")})
            category_name = category["name"] if category else str(product.get("category") or "Uncategorized")
            legacy_images = product.get("images") or []
            legacy_image = next(
                (image for image in legacy_images if image.get("data")),
                None,
            )
            image_record = None
            image_url = ""
            if legacy_image:
                image_id = uuid.uuid4().hex
                image_record = ImageRecord(
                    id=image_id,
                    content_type=legacy_image.get("contentType", "application/octet-stream"),
                    filename=legacy_image.get("filename", ""),
                    data=bytes(legacy_image["data"]),
                    created_at=product.get("updatedAt") or now(),
                )
                image_url = f"/api/images/{image_id}"
            else:
                existing_image_url = product.get("imageUrl")
                if isinstance(existing_image_url, str) and existing_image_url.startswith(
                    ("https://", "/api/images/")
                ):
                    image_url = existing_image_url

            part = Part(
                id=part_id,
                name=product["name"],
                sku=product.get("sku") or f"LEG-{part_id.upper()}",
                category=category_name,
                brand=product.get("brand") or "ZHAGARAM",
                price=product.get("price", 1),
                mrp=product.get("mrp"),
                description=product.get("description") or "",
                specs=product.get("specs") or {},
                imageUrl=image_url,
                createdAt=product.get("createdAt") or now(),
                updatedAt=product.get("updatedAt") or now(),
            )
            if image_record:
                self.insert_image(image_record)
            self.insert_part(part)

    @staticmethod
    def _is_duplicate(exc: Exception) -> bool:
        return type(exc).__name__ == "DuplicateKeyError"

    def is_empty(self) -> bool:
        return self.categories.count_documents({}) == 0 and self.items.count_documents({}) == 0

    def list_categories(self) -> list[Category]:
        return [doc_to_category(d) for d in self.categories.find({}).sort("order", 1)]

    def get_category(self, category_id: str) -> Category | None:
        d = self._find_by_id(self.categories, category_id)
        return doc_to_category(d) if d else None

    def find_category(self, name: str) -> Category | None:
        d = self.categories.find_one({"nameKey": name.casefold()})
        return doc_to_category(d) if d else None

    def insert_category(self, category: Category) -> None:
        try:
            self.categories.insert_one(category_to_doc(category))
        except Exception as exc:
            if self._is_duplicate(exc):
                raise DuplicateCategoryError(f"Category '{category.name}' already exists") from None
            raise

    def replace_category(self, category: Category) -> bool:
        try:
            existing = self._find_by_id(self.categories, category.id)
            if not existing:
                return False
            replacement = category_to_doc(category)
            replacement["_id"] = existing["_id"]
            res = self.categories.replace_one({"_id": existing["_id"]}, replacement)
        except Exception as exc:
            if self._is_duplicate(exc):
                raise DuplicateCategoryError(f"Category '{category.name}' already exists") from None
            raise
        return res.matched_count == 1

    def delete_category(self, category_id: str) -> bool:
        existing = self._find_by_id(self.categories, category_id)
        return bool(existing and self.categories.delete_one({"_id": existing["_id"]}).deleted_count == 1)

    @staticmethod
    def _find_by_id(collection: Any, document_id: str) -> dict[str, Any] | None:
        document = collection.find_one({"_id": document_id})
        if document is None and ObjectId.is_valid(document_id):
            document = collection.find_one({"_id": ObjectId(document_id)})
        return document

    def list_parts(self) -> list[Part]:
        return [doc_to_part(d) for d in self.items.find({})]

    def get_part(self, part_id: str) -> Part | None:
        d = self.items.find_one({"_id": part_id})
        return doc_to_part(d) if d else None

    def insert_part(self, part: Part) -> None:
        try:
            self.items.insert_one(part_to_doc(part))
        except Exception as exc:
            if self._is_duplicate(exc):
                raise DuplicateSkuError(f"SKU '{part.sku}' already exists") from None
            raise

    def replace_part(self, part: Part) -> bool:
        try:
            res = self.items.replace_one({"_id": part.id}, part_to_doc(part))
        except Exception as exc:
            if self._is_duplicate(exc):
                raise DuplicateSkuError(f"SKU '{part.sku}' already exists") from None
            raise
        return res.matched_count == 1

    def delete_part(self, part_id: str) -> bool:
        return self.items.delete_one({"_id": part_id}).deleted_count == 1

    def count_parts(self, category: str) -> int:
        return self.items.count_documents({"category": category})

    def rename_category_in_parts(self, old: str, new: str) -> int:
        return self.items.update_many({"category": old}, {"$set": {"category": new}}).modified_count

    def image_url_in_use(self, url: str, exclude_part_id: str | None = None) -> bool:
        query: dict[str, Any] = {"imageUrl": url}
        if exclude_part_id:
            query["_id"] = {"$ne": exclude_part_id}
        return self.items.count_documents(query, limit=1) > 0

    def insert_image(self, image: ImageRecord) -> None:
        self.images.insert_one(image_to_doc(image))

    def get_image(self, image_id: str) -> ImageRecord | None:
        d = self.images.find_one({"_id": image_id})
        return doc_to_image(d) if d else None

    def delete_image(self, image_id: str) -> bool:
        return self.images.delete_one({"_id": image_id}).deleted_count == 1


def now() -> datetime:
    # MongoDB stores millisecond precision; keep both stores consistent.
    ts = datetime.now(UTC)
    return ts.replace(microsecond=ts.microsecond // 1000 * 1000)
