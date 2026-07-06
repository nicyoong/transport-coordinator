from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from routes_usage import RoutesUsageLimitError, RoutesUsageStore, main


def test_usage_store_migrates_existing_database(tmp_path):
    database_path = tmp_path / "usage.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE route_matrix_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requested_at_utc REAL NOT NULL,
                origin_count INTEGER NOT NULL,
                destination_count INTEGER NOT NULL,
                matrix_element_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT
            )
            """
        )

    RoutesUsageStore(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(route_matrix_requests)"
            )
        }
    assert "api_key_last6" in columns


def test_routes_usage_help_command_does_not_create_database(
    tmp_path,
    capsys,
):
    database_path = tmp_path / "should-not-exist.sqlite3"

    main(["help", "--database", str(database_path)])

    output = capsys.readouterr().out
    assert "commands:" in output
    assert "--api-key-last6" in output
    assert not database_path.exists()


def test_usage_store_counts_requests_and_matrix_elements(tmp_path):
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")
    request_ids = store.reserve_requests([(2, 3), (4, 5)])

    store.set_status(request_ids[0], "succeeded")
    store.set_status(request_ids[1], "failed", "test failure")

    assert store.get_usage_summary() == {
        "window_days": 30,
        "api_key_last6": "all",
        "request_count": 2,
        "matrix_element_count": 26,
        "status_counts": {
            "reserved": 0,
            "succeeded": 1,
            "failed": 1,
        },
    }


def test_usage_store_enforces_limit_atomically(tmp_path):
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")
    first_id = store.reserve_requests(
        [(5, 10)],
        matrix_element_limit=60,
    )[0]
    store.set_status(first_id, "succeeded")

    with pytest.raises(
        RoutesUsageLimitError,
        match=r"50 used \+ 20 requested > 60 elements",
    ):
        store.reserve_requests(
            [(4, 5)],
            matrix_element_limit=60,
        )

    assert store.get_usage_summary()["matrix_element_count"] == 50


def test_usage_limit_is_scoped_to_api_key_suffix(tmp_path):
    store = RoutesUsageStore(tmp_path / "usage.sqlite3")
    first_id = store.reserve_requests(
        [(5, 10)],
        matrix_element_limit=50,
        api_key_last6="first1",
    )[0]
    store.set_status(first_id, "succeeded")

    second_id = store.reserve_requests(
        [(5, 10)],
        matrix_element_limit=50,
        api_key_last6="second",
    )[0]
    store.set_status(second_id, "succeeded")

    assert store.get_usage_summary(api_key_last6="first1")[
        "matrix_element_count"
    ] == 50
    assert store.get_usage_summary(api_key_last6="second")[
        "matrix_element_count"
    ] == 50


def test_usage_store_excludes_cancelled_and_expired_requests(tmp_path):
    current_time = datetime(2026, 7, 6, tzinfo=timezone.utc)
    store = RoutesUsageStore(
        tmp_path / "usage.sqlite3",
        clock=lambda: current_time,
    )

    cancelled_id = store.reserve_requests([(3, 3)])[0]
    store.cancel_requests([cancelled_id])

    old_id = store.reserve_requests([(2, 2)])[0]
    store.set_status(old_id, "succeeded")
    current_time += timedelta(days=31)

    assert store.get_usage_summary()["request_count"] == 0
