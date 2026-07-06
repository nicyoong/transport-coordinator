import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable


class RoutesUsageLimitError(RuntimeError):
    """Raised before an API call would exceed the configured rolling limit."""


class RoutesUsageStore:
    COUNTED_STATUSES = ("reserved", "succeeded", "failed")

    def __init__(
        self,
        database_path: str | Path = "routes_usage.sqlite3",
        clock: Callable[[], datetime] | None = None,
    ):
        self.database_path = Path(database_path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS route_matrix_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requested_at_utc REAL NOT NULL,
                    origin_count INTEGER NOT NULL CHECK (origin_count > 0),
                    destination_count INTEGER NOT NULL
                        CHECK (destination_count > 0),
                    matrix_element_count INTEGER NOT NULL
                        CHECK (matrix_element_count > 0),
                    api_key_last6 TEXT NOT NULL DEFAULT 'unknown',
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'reserved',
                            'succeeded',
                            'failed',
                            'cancelled'
                        )
                    ),
                    error_message TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(route_matrix_requests)"
                )
            }
            if "api_key_last6" not in columns:
                connection.execute(
                    """
                    ALTER TABLE route_matrix_requests
                    ADD COLUMN api_key_last6 TEXT NOT NULL DEFAULT 'unknown'
                    """
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_route_matrix_requests_requested_at
                ON route_matrix_requests (requested_at_utc)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_route_matrix_requests_key_and_time
                ON route_matrix_requests (
                    api_key_last6,
                    requested_at_utc
                )
                """
            )

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Routes usage clock must return a timezone-aware datetime.")
        return now.astimezone(timezone.utc)

    def reserve_requests(
        self,
        request_sizes: Iterable[tuple[int, int]],
        *,
        days: int = 30,
        matrix_element_limit: int | None = None,
        api_key_last6: str = "unknown",
    ) -> list[int]:
        sizes = list(request_sizes)
        if not sizes:
            return []

        for origin_count, destination_count in sizes:
            if origin_count <= 0 or destination_count <= 0:
                raise ValueError("Matrix origin and destination counts must be positive.")

        requested_elements = sum(
            origin_count * destination_count
            for origin_count, destination_count in sizes
        )
        now = self._now()
        cutoff = (now - timedelta(days=days)).timestamp()
        status_placeholders = ",".join("?" for _ in self.COUNTED_STATUSES)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current_elements = connection.execute(
                f"""
                SELECT COALESCE(SUM(matrix_element_count), 0)
                FROM route_matrix_requests
                WHERE requested_at_utc >= ?
                  AND api_key_last6 = ?
                  AND status IN ({status_placeholders})
                """,
                (cutoff, api_key_last6, *self.COUNTED_STATUSES),
            ).fetchone()[0]

            if (
                matrix_element_limit is not None
                and current_elements + requested_elements > matrix_element_limit
            ):
                raise RoutesUsageLimitError(
                    "Routes API rolling usage limit would be exceeded: "
                    f"{current_elements} used + {requested_elements} requested "
                    f"> {matrix_element_limit} elements in {days} days."
                )

            request_ids = []
            for origin_count, destination_count in sizes:
                cursor = connection.execute(
                    """
                    INSERT INTO route_matrix_requests (
                        requested_at_utc,
                        origin_count,
                        destination_count,
                        matrix_element_count,
                        api_key_last6,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, 'reserved')
                    """,
                    (
                        now.timestamp(),
                        origin_count,
                        destination_count,
                        origin_count * destination_count,
                        api_key_last6,
                    ),
                )
                request_ids.append(cursor.lastrowid)

            connection.commit()
            return request_ids
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def set_status(
        self,
        request_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError(f"Invalid final request status: {status}")

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE route_matrix_requests
                SET status = ?, error_message = ?
                WHERE id = ?
                """,
                (status, error_message, request_id),
            )

    def cancel_requests(self, request_ids: Iterable[int]) -> None:
        ids = list(request_ids)
        if not ids:
            return

        placeholders = ",".join("?" for _ in ids)
        with self._connect() as connection:
            connection.execute(
                f"""
                UPDATE route_matrix_requests
                SET status = 'cancelled'
                WHERE id IN ({placeholders}) AND status = 'reserved'
                """,
                ids,
            )

    def get_usage_summary(
        self,
        days: int = 30,
        api_key_last6: str | None = None,
    ) -> dict:
        cutoff = (self._now() - timedelta(days=days)).timestamp()
        status_placeholders = ",".join("?" for _ in self.COUNTED_STATUSES)
        key_filter = ""
        parameters: list[object] = [cutoff]
        if api_key_last6 is not None:
            key_filter = "AND api_key_last6 = ?"
            parameters.append(api_key_last6)
        parameters.extend(self.COUNTED_STATUSES)

        with self._connect() as connection:
            total = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS request_count,
                    COALESCE(SUM(matrix_element_count), 0)
                        AS matrix_element_count
                FROM route_matrix_requests
                WHERE requested_at_utc >= ?
                  {key_filter}
                  AND status IN ({status_placeholders})
                """,
                parameters,
            ).fetchone()
            status_rows = connection.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM route_matrix_requests
                WHERE requested_at_utc >= ?
                  {key_filter}
                  AND status IN ({status_placeholders})
                GROUP BY status
                """,
                parameters,
            ).fetchall()

        status_counts = {status: 0 for status in self.COUNTED_STATUSES}
        status_counts.update({row["status"]: row["count"] for row in status_rows})
        return {
            "window_days": days,
            "api_key_last6": api_key_last6 or "all",
            "request_count": total["request_count"],
            "matrix_element_count": total["matrix_element_count"],
            "status_counts": status_counts,
        }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the local Google Routes matrix usage database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""commands:
  show  Show recorded usage (default).
  help  Show this help message.

examples:
  python routes_usage.py
  python routes_usage.py show --days 7
  python routes_usage.py show --api-key-last6 abc123
  python routes_usage.py show --database routes_usage.sqlite3""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("show", "help"),
        default="show",
        help="Database command to run. Defaults to show.",
    )
    parser.add_argument(
        "--database",
        default="routes_usage.sqlite3",
        help="Path to the Routes usage SQLite database.",
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument(
        "--api-key-last6",
        help="Filter by key suffix; defaults to GOOGLE_MAPS_API_KEY in .env.",
    )
    return parser


def main(arguments=None) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    parser = build_argument_parser()
    args = parser.parse_args(arguments)
    if args.command == "help":
        parser.print_help()
        return

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    api_key_last6 = args.api_key_last6 or (api_key[-6:] if api_key else None)
    store = RoutesUsageStore(args.database)
    print(
        json.dumps(
            store.get_usage_summary(
                args.days,
                api_key_last6=api_key_last6,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
