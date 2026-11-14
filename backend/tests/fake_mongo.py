"""Minimal in-memory stand-in for the pymongo API surface used by MongoStore."""

import copy
from types import SimpleNamespace
from typing import Any

from pymongo.errors import DuplicateKeyError


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict) and "$ne" in cond:
            if value == cond["$ne"]:
                return False
        elif value != cond:
            return False
    return True


class _Cursor(list):
    def sort(self, key: str, direction: int) -> "_Cursor":
        return _Cursor(sorted(self, key=lambda d: d.get(key), reverse=direction < 0))


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.unique: set[str] = {"_id"}

    def create_index(self, key: str, unique: bool = False) -> str:
        if unique:
            self.unique.add(key)
        return key

    def _check_unique(self, doc: dict[str, Any], skip_id: Any = None) -> None:
        for key in self.unique:
            if any(d.get(key) == doc.get(key) and d["_id"] != skip_id for d in self.docs):
                raise DuplicateKeyError(f"duplicate {key}")

    def find(self, query: dict[str, Any]) -> _Cursor:
        return _Cursor(copy.deepcopy(d) for d in self.docs if _matches(d, query))

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next(iter(self.find(query)), None)

    def insert_one(self, doc: dict[str, Any]) -> None:
        self._check_unique(doc)
        self.docs.append(copy.deepcopy(doc))

    def insert_many(self, docs: list[dict[str, Any]]) -> None:
        for doc in docs:
            self.insert_one(doc)

    def replace_one(self, query: dict[str, Any], doc: dict[str, Any]) -> SimpleNamespace:
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                self._check_unique(doc, skip_id=d["_id"])
                self.docs[i] = copy.deepcopy(doc)
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> SimpleNamespace:
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(copy.deepcopy(update.get("$set", {})))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> SimpleNamespace:
        hits = [d for d in self.docs if _matches(d, query)]
        for d in hits:
            d.update(update["$set"])
        return SimpleNamespace(modified_count=len(hits))

    def delete_one(self, query: dict[str, Any]) -> SimpleNamespace:
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                del self.docs[i]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def delete_many(self, query: dict[str, Any]) -> None:
        self.docs = [d for d in self.docs if not _matches(d, query)]

    def count_documents(self, query: dict[str, Any], limit: int | None = None) -> int:
        n = sum(1 for d in self.docs if _matches(d, query))
        return min(n, limit) if limit else n


class FakeDatabase(dict):
    def __missing__(self, name: str) -> FakeCollection:
        self[name] = FakeCollection()
        return self[name]
