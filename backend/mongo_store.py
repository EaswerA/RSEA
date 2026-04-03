import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.errors import ConfigurationError


load_dotenv()


def _get_database():
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/rsea")
    fallback_db_name = os.getenv("MONGODB_DB_NAME", "rsea")

    client = MongoClient(mongodb_uri)
    try:
        database = client.get_default_database()
        if database is not None:
            return client, database
    except ConfigurationError:
        pass

    return client, client[fallback_db_name]


def init_db() -> None:
    client, database = _get_database()
    try:
        database.extractions.create_index([("source_filename", DESCENDING)])
        database.extractions.create_index([("created_at", DESCENDING)])
        database.processing_logs.create_index([("source_filename", DESCENDING)])
        database.processing_logs.create_index([("created_at", DESCENDING)])
    finally:
        client.close()


def store_extractions(items: List[Dict[str, Any]], source_filename: str, output_file: str) -> int:
    rows = []
    created_at = datetime.now(timezone.utc).isoformat()

    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "source_filename": source_filename,
                "output_file": output_file,
                "item_type": item.get("type", ""),
                "component": item.get("component", ""),
                "value": str(item.get("value", "")),
                "unit": item.get("unit", ""),
                "description": item.get("description", ""),
                "confidence": item.get("confidence", None),
                "created_at": created_at,
            }
        )

    if not rows:
        return 0

    client, database = _get_database()
    try:
        result = database.extractions.insert_many(rows)
        return len(result.inserted_ids)
    finally:
        client.close()


def store_processing_log(
    source_filename: str,
    output_file: str,
    items_extracted: int,
    status: str,
    error_message: str = "",
) -> None:
    payload = {
        "source_filename": source_filename,
        "output_file": output_file,
        "items_extracted": items_extracted,
        "status": status,
        "error_message": error_message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    client, database = _get_database()
    try:
        database.processing_logs.insert_one(payload)
    finally:
        client.close()


def get_records(limit: int = 25) -> Dict[str, List[Dict[str, Any]]]:
    safe_limit = max(1, min(limit, 500))

    client, database = _get_database()
    try:
        extractions_cursor = (
            database.extractions.find({}, {"_id": 0})
            .sort([("created_at", DESCENDING)])
            .limit(safe_limit)
        )
        logs_cursor = (
            database.processing_logs.find({}, {"_id": 0})
            .sort([("created_at", DESCENDING)])
            .limit(safe_limit)
        )

        return {
            "extractions": list(extractions_cursor),
            "processing_logs": list(logs_cursor),
        }
    finally:
        client.close()
