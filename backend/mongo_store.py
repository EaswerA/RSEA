import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.errors import ConfigurationError, DuplicateKeyError


load_dotenv()

_TOKEN_SEPARATOR = "."


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
        database.users.create_index([("username", DESCENDING)], unique=True)
        database.extractions.create_index([("source_filename", DESCENDING)])
        database.extractions.create_index([("created_at", DESCENDING)])
        database.extractions.create_index([("username", DESCENDING), ("created_at", DESCENDING)])
        database.processing_logs.create_index([("source_filename", DESCENDING)])
        database.processing_logs.create_index([("created_at", DESCENDING)])
        database.processing_logs.create_index([("username", DESCENDING), ("created_at", DESCENDING)])
    finally:
        client.close()


def _get_secret_key() -> str:
    secret = os.getenv("APP_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET_KEY is missing or too short. Set APP_SECRET_KEY to at least 32 characters.")
    return secret


def _hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return derived.hex()


def create_user(username: str, password: str) -> bool:
    normalized_username = username.strip().lower()
    if not normalized_username or not password:
        return False

    salt = secrets.token_hex(16)
    payload = {
        "username": normalized_username,
        "password_salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    client, database = _get_database()
    try:
        existing = database.users.find_one({"username": normalized_username}, {"_id": 1})
        if existing:
            return False
        try:
            database.users.insert_one(payload)
        except DuplicateKeyError:
            return False
        return True
    finally:
        client.close()


def verify_user(username: str, password: str) -> bool:
    normalized_username = username.strip().lower()
    client, database = _get_database()
    try:
        user = database.users.find_one({"username": normalized_username})
        if not user:
            return False

        expected_hash = user.get("password_hash", "")
        salt = user.get("password_salt", "")
        candidate_hash = _hash_password(password, salt)
        return hmac.compare_digest(expected_hash, candidate_hash)
    finally:
        client.close()


def issue_token(username: str, ttl_seconds: int = 8 * 60 * 60) -> str:
    normalized_username = username.strip().lower()
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{normalized_username}|{expires_at}"
    signature = hmac.new(_get_secret_key().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}{_TOKEN_SEPARATOR}{signature}"


def verify_token(token: str) -> str | None:
    if not token or _TOKEN_SEPARATOR not in token:
        return None

    payload, signature = token.rsplit(_TOKEN_SEPARATOR, 1)
    expected_signature = hmac.new(
        _get_secret_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        username, expires_at_raw = payload.split("|", 1)
        expires_at = int(expires_at_raw)
    except ValueError:
        return None

    if time.time() > expires_at:
        return None

    return username


def store_extractions(
    items: List[Dict[str, Any]],
    source_filename: str,
    output_file: str,
    username: str,
) -> int:
    rows = []
    created_at = datetime.now(timezone.utc).isoformat()

    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "source_filename": source_filename,
                "username": username,
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
    username: str,
    error_message: str = "",
) -> None:
    payload = {
        "source_filename": source_filename,
        "username": username,
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


def get_records(username: str, limit: int = 25) -> Dict[str, List[Dict[str, Any]]]:
    safe_limit = max(1, min(limit, 500))
    query = {"username": username}

    client, database = _get_database()
    try:
        extractions_cursor = (
            database.extractions.find(query, {"_id": 0})
            .sort([("created_at", DESCENDING)])
            .limit(safe_limit)
        )
        logs_cursor = (
            database.processing_logs.find(query, {"_id": 0})
            .sort([("created_at", DESCENDING)])
            .limit(safe_limit)
        )

        return {
            "extractions": list(extractions_cursor),
            "processing_logs": list(logs_cursor),
        }
    finally:
        client.close()
