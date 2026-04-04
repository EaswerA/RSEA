import os
import sqlite3
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("SQLITE_DB_PATH", "rsea.sqlite")


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            create table if not exists extractions (
                id integer primary key autoincrement,
                source_filename text not null,
                output_file text not null,
                item_type text not null,
                component text not null,
                value text,
                unit text,
                description text,
                confidence real,
                created_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            """
            create table if not exists processing_logs (
                id integer primary key autoincrement,
                source_filename text not null,
                output_file text,
                items_extracted integer not null default 0,
                status text not null,
                error_message text,
                created_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            "create index if not exists idx_extractions_source_filename on extractions(source_filename)"
        )
        connection.execute(
            "create index if not exists idx_extractions_created_at on extractions(created_at desc)"
        )
        connection.execute(
            "create index if not exists idx_processing_logs_source_filename on processing_logs(source_filename)"
        )
        connection.execute(
            "create index if not exists idx_processing_logs_created_at on processing_logs(created_at desc)"
        )


def store_extractions(items: List[Dict[str, Any]], source_filename: str, output_file: str) -> int:
    if not items:
        return 0

    rows = [
        (
            source_filename,
            output_file,
            item.get("type", ""),
            item.get("component", ""),
            str(item.get("value", "")),
            item.get("unit", ""),
            item.get("description", ""),
            item.get("confidence", None),
        )
        for item in items
        if isinstance(item, dict)
    ]

    with get_connection() as connection:
        connection.executemany(
            """
            insert into extractions (
                source_filename,
                output_file,
                item_type,
                component,
                value,
                unit,
                description,
                confidence
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    return len(rows)


def store_processing_log(
    source_filename: str,
    output_file: str,
    items_extracted: int,
    status: str,
    error_message: str = "",
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            insert into processing_logs (
                source_filename,
                output_file,
                items_extracted,
                status,
                error_message
            ) values (?, ?, ?, ?, ?)
            """,
            (
                source_filename,
                output_file,
                items_extracted,
                status,
                error_message,
            ),
        )