# ZHAGARAM Jewellery

Responsive imitation / fashion jewellery catalogue (buy or rent) with an admin console.

- **Frontend:** Angular 19 (standalone components, signals) — `frontend/`
- **Backend:** FastAPI (Python 3.11+) — `backend/`
- **Database:** MongoDB (items, categories **and images**). Until a connection string is configured, the same documents are kept in local JSON files.

| Role | Access |
|------|--------|
| Visitor | Browse, search, filter by category, sort, view details, and **download item images**. No login is required. |
| Admin | Sign in at `/admin/login`. Add, edit, and delete jewellery, upload images, and **add, rename, or delete categories**. |

Default admin credentials (local/demo): `admin_zha` / `zhagaram`. You can override them in `backend/.env`.

## Run locally

```powershell
# 1. Backend (http://localhost:8000, docs at /docs)
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --reload-dir app --port 8000

# 2. Frontend (http://localhost:4200, proxies /api to :8000)
cd frontend
npm install
npx ng serve
```

`GET /api/health` reports which storage is active (`"storage": "mongo"` or `"json"`).

## Storage and MongoDB

| `MONGO_URI` | Storage used | Location |
|-------------|--------------|----------|
| set | **MongoDB** | collections `categories`, `items`, `images` in database `MONGO_DB` (default `zhagaram`) |
| empty | JSON fallback | `backend/data/categories.json`, `items.json`, `images.json` (images stored as base64) |

On startup, legacy MongoDB `products` are copied into `items` for the current API, and legacy category fields are normalized. The source product documents are retained.

Images live in the database and are served from `GET /api/images/{id}`. There are no static image files. On first start with an empty database, the backend loads the seed catalogue: 11 categories, 19 designs, and their illustrations from `backend/app/seed_images/`.

### Connecting MongoDB later

1. Copy `backend/.env.example` to `backend/.env` and set `MONGO_URI` (and optionally `MONGO_DB`).
2. Load the current catalogue into MongoDB using **one** of these methods:
   - Run `.\.venv\Scripts\python -m app.tools import` from `backend/`. This reads the files in `mongo-export/` and creates indexes. Add `--replace` to overwrite a non-empty database.
   - Use `mongoimport` with the exported files:
     ```bash
     mongoimport --uri "$MONGO_URI" --db zhagaram --collection categories --jsonArray --file mongo-export/categories.json
     mongoimport --uri "$MONGO_URI" --db zhagaram --collection items      --jsonArray --file mongo-export/items.json
     mongoimport --uri "$MONGO_URI" --db zhagaram --collection images     --jsonArray --file mongo-export/images.json
     ```
   - Skip importing. An empty MongoDB database is seeded automatically on first start.
3. Restart the backend. `/api/health` should then report `"storage": "mongo"`.

To refresh `mongo-export/` from the live data (including admin changes), run `.\.venv\Scripts\python -m app.tools export` from `backend/`.

### Document shapes

- `categories`: `_id`, `name`, `nameKey` (unique, lower-case), `rental` (priced per day), `order`, `createdAt`
- `items`: `_id`, `name`, `sku`, `skuKey` (unique, lower-case), `category` (category name), `brand`, `price`, `mrp`, `description`, `specs`, `imageUrl` (`/api/images/{id}`), `createdAt`, `updatedAt`
- `images`: `_id`, `contentType`, `filename`, `size`, `data` (binary), `createdAt`

## Tests and build

```powershell
cd backend;  .\.venv\Scripts\python -m pytest -q   # runs every API test against both the JSON and MongoDB stores
cd frontend; npx ng build
```

## API

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/parts?search=&category=&sort=newest\|price_asc\|price_desc\|name` | Public |
| GET | `/api/parts/{id}` | Public |
| GET | `/api/categories` (includes `rental` and `itemCount`) | Public |
| GET | `/api/images/{id}` | Public |
| GET | `/api/images/{id}/download?filename=` (sent as a file attachment) | Public |
| POST | `/api/auth/login` | Public |
| POST / PUT / DELETE | `/api/parts[/{id}]` | Bearer JWT |
| POST / PUT / DELETE | `/api/categories[/{id}]` (delete is refused with 409 while items use the category; rename updates its items) | Bearer JWT |
| POST | `/api/uploads` (multipart `file`; JPG/PNG/WEBP up to 2 MB, stored in the database) | Bearer JWT |

## Notes

- **Deleted images:** when an item is deleted or its image is replaced, the old image is removed from the database if no other item uses it.
- **JSON fallback:** the JSON store is safe for a **single backend process** only. MongoDB has no such limit.
- **Admin sessions:** if you don't set `JWT_SECRET`, the backend generates a random secret at startup, so admin sessions end when the backend restarts.
- **Older data:** a pre-database `backend/data/parts.json`, and its `backend/uploads/` images, is migrated automatically on first start and then renamed to `parts.legacy.json`.

> Internal code names (`Part`, `/api/parts`) are kept from the first version; all user-facing text refers to jewellery.
