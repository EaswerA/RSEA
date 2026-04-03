import os
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import ConfigurationError


load_dotenv()


def get_mongo_database(uri: str, fallback_name: str):
    client = MongoClient(uri)
    try:
        db = client.get_default_database()
        if db is not None:
            return client, db
    except ConfigurationError:
        pass
    return client, client[fallback_name]


def fetch_rows(connection: sqlite3.Connection, table_name: str):
    cursor = connection.execute(f"select * from {table_name}")
    return [dict(row) for row in cursor.fetchall()]


def build_upserts(rows, id_field_name: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    operations = []
    for row in rows:
        sqlite_id = row.get("id")
        row[id_field_name] = sqlite_id
        row["migrated_at"] = now_iso
        operations.append(
            UpdateOne(
                {id_field_name: sqlite_id},
                {"$set": row},
                upsert=True,
            )
        )
    return operations


def main():
    sqlite_db_path = os.getenv("SQLITE_DB_PATH", "rsea.sqlite")
    mongodb_uri = os.getenv("MONGODB_URI")
    mongodb_db_name = os.getenv("MONGODB_DB_NAME", "rsea")

    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set in environment.")

    if not os.path.exists(sqlite_db_path):
        raise FileNotFoundError(f"SQLite database not found at: {sqlite_db_path}")

    with sqlite3.connect(sqlite_db_path) as connection:
        connection.row_factory = sqlite3.Row
        extraction_rows = fetch_rows(connection, "extractions")
        processing_log_rows = fetch_rows(connection, "processing_logs")

    client, database = get_mongo_database(mongodb_uri, mongodb_db_name)

    try:
        extraction_ops = build_upserts(extraction_rows, "sqlite_id")
        processing_log_ops = build_upserts(processing_log_rows, "sqlite_id")

        extraction_result = None
        processing_log_result = None

        if extraction_ops:
            extraction_result = database.extractions.bulk_write(extraction_ops, ordered=False)

        if processing_log_ops:
            processing_log_result = database.processing_logs.bulk_write(processing_log_ops, ordered=False)

        print(f"SQLite source: {sqlite_db_path}")
        print(f"MongoDB target: {database.name}")
        print(f"extractions rows read: {len(extraction_rows)}")
        print(f"processing_logs rows read: {len(processing_log_rows)}")

        if extraction_result is not None:
            print(
                "extractions upserted:",
                extraction_result.upserted_count,
                "modified:",
                extraction_result.modified_count,
            )
        else:
            print("extractions upserted: 0 modified: 0")

        if processing_log_result is not None:
            print(
                "processing_logs upserted:",
                processing_log_result.upserted_count,
                "modified:",
                processing_log_result.modified_count,
            )
        else:
            print("processing_logs upserted: 0 modified: 0")
    finally:
        client.close()


if __name__ == "__main__":
    main()
