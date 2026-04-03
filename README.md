# RSEA

## Local Run

The app runs locally and exports extracted rows to Excel in the `outputs` folder.

## MongoDB Storage

The app stores extracted rows and processing logs in MongoDB.

Set `MONGODB_URI` in `.env` (example: `mongodb://localhost:27017/rsea`).

Optionally set `MONGODB_DB_NAME` if your URI does not include a default database name.

Use `GET /records/` in the browser or Swagger UI to view the latest stored rows and logs.

## Legacy Migration (SQLite to MongoDB)

Set `MONGODB_URI` in `.env`, then run:

`python backend/migrate_sqlite_to_mongodb.py`

This copies rows from `extractions` and `processing_logs` in SQLite into MongoDB collections with idempotent upserts.