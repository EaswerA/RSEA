# RSEA

RSEA extracts hardware/software requirements from uploaded tender PDFs, saves extracted results to Excel, and stores extraction records in MongoDB.

## What Is Implemented

- FastAPI backend for upload/extraction APIs
- Username/password authentication with token-based sessions
- User-isolated uploads, outputs, and records
- Gemini-based extraction pipeline (model-first)
- MongoDB as runtime storage
- Frontend dashboard for upload + viewing latest records
- Legacy migration script from SQLite to MongoDB

## Project Structure

```text
backend/
	app.py                         FastAPI app and route wiring
	extractor.py                   Gemini extraction logic
	normalizer.py                  Data normalization
	parser.py                      PDF text extraction
	excel_writer.py                Excel output writer
	mongo_store.py                 MongoDB read/write layer
	migrate_sqlite_to_mongodb.py   One-time migration utility

frontend/
	index.html                     Dashboard UI
	assets/
		styles.css                   Frontend styling
		app.js                       Frontend API integration

outputs/                         Generated Excel files
uploads/                         Uploaded PDFs
tests/                           Smoke tests
```

## Prerequisites

- Python 3.14+
- MongoDB Community Server running locally
- (Optional) MongoDB Shell (`mongosh`) for DB inspection

## Environment Setup

1. Create and activate virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure `.env` in project root:

```env
GEMINI_API_KEY=your_key_here
MONGODB_URI=mongodb://localhost:27017/rsea
GEMINI_MODEL_CANDIDATES=gemini-2.0-flash,gemini-1.5-flash,gemini-2.5-flash,gemini-2.5-pro
```

Optional variables:

- `MONGODB_DB_NAME=rsea` (when URI has no database suffix)
- `GEMINI_MODEL=gemini-2.5-flash` (force a single model)

## Run Locally

From project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open URLs:

- Frontend: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- Records API: http://127.0.0.1:8000/records/?limit=25

Download generated output files:

- Requires a valid session token (frontend handles this automatically)

## Frontend Usage

1. Open frontend URL.
2. Register a user account (first time only), then log in.
3. Choose a PDF file.
4. Click `Extract Now`.
5. Review `Latest Records` tables (shows only your own records).
6. Click output filename links to download your files.

## Backend API Endpoints

- `GET /` -> serves frontend dashboard
- `GET /docs` -> Swagger UI
- `POST /auth/register` -> create username/password account
- `POST /auth/login` -> obtain session token
- `GET /auth/me` -> validate current token and return logged-in username
- `POST /upload/` -> upload PDF and run extraction
- `GET /records/?limit=25` -> latest extraction rows + processing logs for logged-in user
- `GET /files/{filename}?token=...` -> authenticated output file download

## MongoDB Storage Model

Collections used:

- `users`
- `extractions`
- `processing_logs`

Common fields in `extractions`:

- `source_filename`, `output_file`
- `item_type`, `component`, `value`, `unit`
- `description`, `confidence`, `created_at`

Common fields in `processing_logs`:

- `source_filename`, `output_file`
- `items_extracted`, `status`, `error_message`, `created_at`

## Useful MongoDB Commands (PowerShell)

```powershell
$mongosh = "C:\Users\ASUS\AppData\Local\Programs\mongosh\mongosh.exe"
```

Show collections:

```powershell
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "show collections"
```

Counts per collection:

```powershell
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "db.getCollectionNames().forEach(function(c){ print(c + ': ' + db.getCollection(c).countDocuments()); })"
```

Distinct stored source/output files:

```powershell
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "print('Source files:'); printjson(db.extractions.distinct('source_filename')); print('Output files:'); printjson(db.extractions.distinct('output_file'));"
```

## Gemini Model Behavior

- Extraction uses Gemini models only.
- Candidate models are tried in order from `GEMINI_MODEL_CANDIDATES`.
- If one model fails (quota/access/temporary error), the next candidate is tried.
- If all candidates fail, upload returns `503 Extraction failed`.

### Confidence Score Notes

- Confidence is returned by Gemini output.

## Migration: SQLite to MongoDB (Legacy Data)

Run once if old SQLite data exists:

```powershell
python backend/migrate_sqlite_to_mongodb.py
```

This performs idempotent upserts into MongoDB collections.

## Run Tests

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

## Troubleshooting

### 1) Port 8000 already in use

```powershell
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force }
```

### 2) Gemini quota/access errors

- Verify API key is valid and not expired.
- Ensure billing/quota exists for the project behind the key.
- Keep fallback candidate models configured.
- Test candidate model availability before upload.

### 3) MongoDB connectivity issues

- Ensure MongoDB service is running.
- Verify `MONGODB_URI` points to active local instance.

### 4) Upload dependency error (`python-multipart`)

```powershell
pip install -r requirements.txt
```

## Notes

- `uploads/` and `outputs/` grow over time from test runs.
- Keep `.env` private and never commit real API keys.
