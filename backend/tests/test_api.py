import json

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.bootstrap import bootstrap
from app.config import Settings, get_settings
from app.deps import get_store
from app.main import app
from app.seed import SEED_CATEGORIES, SEED_PARTS
from app.storage import JsonStore, MongoStore, now
from app.tools import export_store, import_into
from tests.fake_mongo import FakeDatabase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
NEW_PART = {
    "name": "Test Peacock Earrings",
    "sku": "TST-EAR-999",
    "category": "Earrings",
    "brand": "ZHAGARAM Test",
    "price": 2500,
}


def make_settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        legacy_data_file=tmp_path / "legacy" / "parts.json",
        legacy_upload_dir=tmp_path / "legacy" / "uploads",
        jwt_secret="test-secret-" + "x" * 32,
    )


def make_store(kind: str, settings: Settings):
    return JsonStore(settings.data_dir) if kind == "json" else MongoStore(FakeDatabase())


@pytest.fixture(params=["json", "mongo"])
def store(request, tmp_path):
    settings = make_settings(tmp_path)
    store = make_store(request.param, settings)
    bootstrap(store, settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def client(store):
    return TestClient(app)


@pytest.fixture
def auth(client):
    res = client.post("/api/auth/login", json={"username": "admin_zha", "password": "zhagaram"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def test_public_listing_filters_and_sorts(client):
    assert len(client.get("/api/parts").json()) == len(SEED_PARTS)
    rings = client.get("/api/parts", params={"category": "Rings"}).json()
    assert rings and all(p["category"] == "Rings" for p in rings)
    prices = [p["price"] for p in client.get("/api/parts", params={"sort": "price_asc"}).json()]
    assert prices == sorted(prices)
    jhumkas = {p["sku"] for p in client.get("/api/parts", params={"search": "jhumka"}).json()}
    assert jhumkas == {"EAR-JHM-004", "BRD-SET-016"}


def test_seed_images_are_served_from_the_database(client):
    part = client.get("/api/parts").json()[0]
    assert part["imageUrl"].startswith("/api/images/")
    res = client.get(part["imageUrl"])
    assert res.status_code == 200 and res.headers["content-type"].startswith("image/svg+xml")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/images/" + "0" * 32).status_code == 404
    assert client.get("/api/images/../etc").status_code == 404


def test_image_download_sets_safe_attachment_filename(client):
    url = client.get("/api/parts").json()[0]["imageUrl"]
    res = client.get(f"{url}/download", params={"filename": 'Ruby "Jhumka"/../x'})
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="Ruby-Jhumka-x.svg"'
    fallback = client.get(f"{url}/download")
    assert 'filename="zhagaram-jewellery.svg"' in fallback.headers["content-disposition"]


def test_categories_listed_with_rental_flag_and_counts(client):
    cats = client.get("/api/categories").json()
    assert [c["name"] for c in cats] == [name for name, _ in SEED_CATEGORIES]
    rent = next(c for c in cats if c["name"] == "Rent")
    assert rent["rental"] is True and rent["itemCount"] == 3


def test_login_rejects_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "admin_zha", "password": "nope"})
    assert res.status_code == 401


def test_writes_require_admin(client):
    assert client.post("/api/parts", json=NEW_PART).status_code == 401
    assert client.post("/api/categories", json={"name": "Toe Rings"}).status_code == 401
    assert client.delete("/api/parts/x", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_admin_item_crud_round_trip(client, auth):
    created = client.post("/api/parts", json={**NEW_PART, "category": "earrings"}, headers=auth)
    assert created.status_code == 201 and created.json()["category"] == "Earrings"
    part_id = created.json()["id"]

    assert client.post("/api/parts", json={**NEW_PART, "sku": "tst-ear-999"}, headers=auth).status_code == 409
    unknown = client.post("/api/parts", json={**NEW_PART, "sku": "X-1", "category": "Crowns"}, headers=auth)
    assert unknown.status_code == 422

    updated = client.put(f"/api/parts/{part_id}", json={**NEW_PART, "price": 2999}, headers=auth)
    assert updated.status_code == 200 and updated.json()["price"] == 2999

    assert client.delete(f"/api/parts/{part_id}", headers=auth).status_code == 204
    assert client.get(f"/api/parts/{part_id}").status_code == 404


def test_rejects_unknown_fields_and_foreign_image_urls(client, auth):
    assert client.post("/api/parts", json={**NEW_PART, "hack": 1}, headers=auth).status_code == 422
    bad = {**NEW_PART, "imageUrl": "javascript:alert(1)"}
    assert client.post("/api/parts", json=bad, headers=auth).status_code == 422


def test_category_lifecycle(client, auth):
    res = client.post("/api/categories", json={"name": "Toe Rings", "rental": False}, headers=auth)
    assert res.status_code == 201
    cat = res.json()
    assert client.get("/api/categories").json()[-1]["name"] == "Toe Rings"
    assert client.post("/api/categories", json={"name": "toe rings"}, headers=auth).status_code == 409

    item = client.post("/api/parts", json={**NEW_PART, "category": "Toe Rings"}, headers=auth).json()
    blocked = client.delete(f"/api/categories/{cat['id']}", headers=auth)
    assert blocked.status_code == 409 and "1 item" in blocked.json()["detail"]

    renamed = client.put(f"/api/categories/{cat['id']}", json={"name": "Metti", "rental": True}, headers=auth)
    assert renamed.status_code == 200 and renamed.json()["itemCount"] == 1
    assert client.get(f"/api/parts/{item['id']}").json()["category"] == "Metti"

    assert client.delete(f"/api/parts/{item['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/categories/{cat['id']}", headers=auth).status_code == 204
    assert all(c["name"] != "Metti" for c in client.get("/api/categories").json())


def test_upload_stores_image_in_db_and_cleans_up_orphans(client, auth, store):
    up = client.post("/api/uploads", files={"file": ("a.png", PNG, "image/png")}, headers=auth)
    assert up.status_code == 201
    url = up.json()["imageUrl"]
    assert client.get(url).content == PNG

    item = client.post("/api/parts", json={**NEW_PART, "imageUrl": url}, headers=auth).json()
    assert client.delete(f"/api/parts/{item['id']}", headers=auth).status_code == 204
    assert client.get(url).status_code == 404

    fake = client.post("/api/uploads", files={"file": ("a.png", b"<svg/>", "image/png")}, headers=auth)
    assert fake.status_code == 415
    svg = client.post("/api/uploads", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")}, headers=auth)
    assert svg.status_code == 415


def test_legacy_json_file_is_migrated_into_the_store(tmp_path):
    settings = make_settings(tmp_path)
    settings.legacy_upload_dir.mkdir(parents=True)
    (settings.legacy_upload_dir / "u1.png").write_bytes(PNG)
    settings.legacy_data_file.write_text(json.dumps([
        {"id": "a", "name": "Old ring", "sku": "OLD-1", "category": "Rings", "brand": "X", "price": 10,
         "stock": 4, "compatibleVehicles": ["Ford Figo"], "imageUrl": "/uploads/u1.png",
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "Old crown", "sku": "OLD-2", "category": "Crowns", "brand": "X", "price": 20,
         "imageUrl": "/static/items/ruby-jhumka.svg",
         "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
    ]), encoding="utf-8")
    store = JsonStore(settings.data_dir)
    bootstrap(store, settings)

    ring, crown = store.get_part("a"), store.get_part("b")
    assert store.get_image(ring.image_url.rsplit("/", 1)[-1]).data == PNG
    assert store.get_image(crown.image_url.rsplit("/", 1)[-1]).content_type == "image/svg+xml"
    assert store.find_category("Crowns") is not None
    assert not settings.legacy_data_file.exists()
    assert settings.legacy_data_file.with_suffix(".legacy.json").exists()


def test_export_then_import_into_mongo_round_trips(tmp_path):
    settings = make_settings(tmp_path)
    source = JsonStore(settings.data_dir)
    bootstrap(source, settings)

    counts = export_store(source, tmp_path / "export")
    assert counts == {"categories": len(SEED_CATEGORIES), "items": len(SEED_PARTS), "images": 19}

    target = MongoStore(FakeDatabase())
    import_into(target, tmp_path / "export", replace=False)
    part = source.list_parts()[0]
    copied = target.get_part(part.id)
    assert copied == part
    image_id = part.image_url.rsplit("/", 1)[-1]
    assert target.get_image(image_id).data == source.get_image(image_id).data
    with pytest.raises(SystemExit):
        import_into(target, tmp_path / "export", replace=False)


def test_legacy_mongo_catalogue_is_migrated_and_get_routes_work(tmp_path):
    settings = make_settings(tmp_path)
    db = FakeDatabase()
    category_id = ObjectId()
    product_id = ObjectId()
    db["categories"].insert_one({
        "_id": category_id,
        "name": "Chains",
        "createdAt": now(),
    })
    db["products"].insert_one({
        "_id": product_id,
        "name": "Legacy Chain",
        "description": "A legacy product",
        "price": 1000,
        "category": category_id,
        "images": [{"data": PNG, "contentType": "image/png"}],
        "createdAt": now(),
        "updatedAt": now(),
    })

    MongoStore._normalize_legacy_categories(db["categories"])
    store = MongoStore(db)
    store._migrate_legacy_products(db["products"])
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            categories = client.get("/api/categories")
            assert categories.status_code == 200
            category = categories.json()[0]
            assert category["id"] == str(category_id)
            assert category["name"] == "Chains"
            assert category["rental"] is False
            assert category["itemCount"] == 1

            parts = client.get("/api/parts")
            assert parts.status_code == 200
            part = parts.json()[0]
            assert part["id"] == str(product_id)
            assert part["category"] == "Chains"
            assert part["sku"] == f"LEG-{str(product_id).upper()}"
            assert client.get(f"/api/parts/{part['id']}").status_code == 200
            image = client.get(part["imageUrl"])
            assert image.status_code == 200
            assert image.content == PNG
    finally:
        app.dependency_overrides.clear()
