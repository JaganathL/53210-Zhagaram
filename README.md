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
| set | **MongoDB** | collections `categories`, `items`, `images` in database `MONGO_DB` (default `zhagaram-jewellery`) |
| empty | JSON fallback | `backend/data/categories.json`, `items.json`, `images.json` (images stored as base64) |

On startup, legacy MongoDB `products` are copied into `items` for the current API, and legacy category fields are normalized. The source product documents are retained.

Images live in the database and are served from `GET /api/images/{id}`. There are no static image files. On first start with an empty database, the backend loads the seed catalogue: 11 categories, 19 designs, and their illustrations from `backend/app/seed_images/`.

### Deploying the backend on Vercel

Vercel does not use the local `backend/.env` file. Add `MONGO_URI` (a hosted MongoDB connection string), `MONGO_DB=zhagaram-jewellery`, and `STORAGE=mongo` to the Vercel project's environment variables, then redeploy. Do not use a `127.0.0.1` MongoDB URI on Vercel. The JSON file store is not persistent serverless storage. `/api/health` should report `"storage":"mongo"` after deployment.

### Deploying the backend on Cloudflare

The Cloudflare deployment uses [Containers](https://developers.cloudflare.com/containers/), so it runs the existing FastAPI app rather than requiring a rewrite as a Worker. Cloudflare Containers require a Workers Paid plan, and deploying the image requires Docker Desktop (or another Docker-compatible engine) to be running.

The deployment files are `backend/Dockerfile`, `backend/wrangler.jsonc`, and `backend/cloudflare/src/index.js`. The Worker forwards API requests to the container on port 8000 and checks `/api/health` before forwarding traffic. The container uses MongoDB; it does not use the local JSON files.

1. Make sure MongoDB Atlas is reachable from Cloudflare Containers, and update `CORS_ORIGINS` in `backend/wrangler.jsonc` to a JSON array containing the deployed frontend origin, for example `["https://your-site.pages.dev"]`.
2. From `backend/`, log in and deploy the Worker:
   ```powershell
   npx wrangler login
   npx wrangler deploy
   ```
3. Add the required Worker secrets when prompted:
   ```powershell
   npx wrangler secret put MONGO_URI
   npx wrangler secret put JWT_SECRET
   npx wrangler secret put ADMIN_PASSWORD
   ```
   `MONGO_URI` must be a hosted MongoDB connection string. The Worker passes these secrets to the container at startup.
4. Test `https://zhagaram-api.<your-workers-subdomain>.workers.dev/api/health` and `/api/categories`. Health should report `"storage":"mongo"`. The first Container deployment may take several minutes to provision.

The `frontend/proxy.conf.json` file is only used by the local Angular development server. For production, route the frontend's `/api` requests to this Worker (for example, through a custom domain or a frontend API base URL). Ensure the deployed frontend origin is included in `CORS_ORIGINS`.

### Connecting MongoDB later

1. Copy `backend/.env.example` to `backend/.env` and set `MONGO_URI` (and optionally `MONGO_DB`).
2. Load the current catalogue into MongoDB using **one** of these methods:
   - Run `.\.venv\Scripts\python -m app.tools import` from `backend/`. This reads the files in `mongo-export/` and creates indexes. Add `--replace` to overwrite a non-empty database.
   - Use `mongoimport` with the exported files:
     ```bash
     mongoimport --uri "$MONGO_URI" --db zhagaram-jewellery --collection categories --jsonArray --file mongo-export/categories.json
     mongoimport --uri "$MONGO_URI" --db zhagaram-jewellery --collection items      --jsonArray --file mongo-export/items.json
     mongoimport --uri "$MONGO_URI" --db zhagaram-jewellery --collection images     --jsonArray --file mongo-export/images.json
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
