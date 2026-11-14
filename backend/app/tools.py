"""Export the catalogue as MongoDB-ready JSON, or import it into MongoDB.

    python -m app.tools export [--dir ../mongo-export]
    python -m app.tools import [--dir ../mongo-export] [--replace]    # needs MONGO_URI

Exported files are MongoDB Extended JSON arrays, so they also work with:
    mongoimport --uri "$MONGO_URI" --db zhagaram-jewellery --collection items --jsonArray --file items.json
"""

import argparse
import sys
from datetime import UTC
from pathlib import Path

from bson import json_util

from .bootstrap import image_id_from_url
from .config import BASE_DIR, get_settings
from .storage import MongoStore, Store, category_to_doc, image_to_doc, part_to_doc

DEFAULT_DIR = BASE_DIR.parent / "mongo-export"
COLLECTIONS = ("categories", "items", "images")
_JSON_OPTS = json_util.RELAXED_JSON_OPTIONS.with_options(tz_aware=True, tzinfo=UTC)


def export_store(store: Store, out_dir: Path) -> dict[str, int]:
    parts = store.list_parts()
    image_ids = {i for p in parts if (i := image_id_from_url(p.image_url))}
    images = [img for i in sorted(image_ids) if (img := store.get_image(i))]
    docs = {
        "categories": [category_to_doc(c) for c in store.list_categories()],
        "items": [part_to_doc(p) for p in parts],
        "images": [image_to_doc(i) for i in images],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in docs.items():
        (out_dir / f"{name}.json").write_text(
            json_util.dumps(rows, json_options=_JSON_OPTS, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return {name: len(rows) for name, rows in docs.items()}


def import_into(store: MongoStore, in_dir: Path, replace: bool) -> dict[str, int]:
    if not store.is_empty() and not replace:
        raise SystemExit("Target database is not empty. Re-run with --replace to overwrite it.")
    counts: dict[str, int] = {}
    for name in COLLECTIONS:
        collection = getattr(store, name)
        rows = json_util.loads((in_dir / f"{name}.json").read_text(encoding="utf-8"), json_options=_JSON_OPTS)
        if replace:
            collection.delete_many({})
        if rows:
            collection.insert_many(rows)
        counts[name] = len(rows)
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.tools")
    parser.add_argument("command", choices=["export", "import"])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--replace", action="store_true", help="import: overwrite existing data")
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "export":
        from .deps import get_store

        counts = export_store(get_store(), args.dir)
    else:
        if not settings.mongo_uri:
            sys.exit("Set MONGO_URI (environment or backend/.env) before importing.")
        counts = import_into(MongoStore.connect(settings.mongo_uri, settings.mongo_db), args.dir, args.replace)
    print(f"{args.command}: {counts} ({args.dir})")


if __name__ == "__main__":
    main()
