# RSEA

RSEA extracts requirements from uploaded PDF files, writes Excel output files to `outputs`, and stores extraction records in MongoDB.

## Prerequisites

- Python 3.14+
- MongoDB Community Server (running locally)
- MongoDB Shell (`mongosh`) (optional, for checking data)

## Environment Setup

1. Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create or update `.env` in project root.

Example:

```env
GEMINI_API_KEY=your_key_here
MONGODB_URI=mongodb://localhost:27017/rsea
```

Optional:

- `MONGODB_DB_NAME=rsea` (only needed if URI does not include database name)

## Run The Project (Localhost)

Start the API server:

```powershell
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open in browser:

- App root: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Stored records endpoint: http://localhost:8000/records/?limit=25

## MongoDB Storage Details

The app writes to MongoDB collections:

- `extractions`
- `processing_logs`

Check collections:

```powershell
$mongosh = "C:\Users\ASUS\AppData\Local\Programs\mongosh\mongosh.exe"
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "show collections"
```

Check collection counts:

```powershell
$mongosh = "C:\Users\ASUS\AppData\Local\Programs\mongosh\mongosh.exe"
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "db.getCollectionNames().forEach(function(c){ print(c + ': ' + db.getCollection(c).countDocuments()); })"
```

List stored source/output filenames:

```powershell
$mongosh = "C:\Users\ASUS\AppData\Local\Programs\mongosh\mongosh.exe"
& $mongosh "mongodb://localhost:27017/rsea" --quiet --eval "print('Source files:'); printjson(db.extractions.distinct('source_filename')); print('Output files:'); printjson(db.extractions.distinct('output_file'));"
```

## Legacy Migration (SQLite to MongoDB)

If you have existing SQLite data, migrate once with:

```powershell
python backend/migrate_sqlite_to_mongodb.py
```

This upserts rows from SQLite tables into MongoDB collections without creating duplicates on rerun.

## Troubleshooting

- If localhost is not opening, check if port 8000 is already in use.
- If uploads fail at startup with multipart error, install dependencies again: `pip install -r requirements.txt`.
- If MongoDB connection fails, confirm MongoDB service is running and `MONGODB_URI` is correct.