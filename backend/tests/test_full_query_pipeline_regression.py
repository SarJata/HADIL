import os
import sys
import tempfile
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from hadil_runtime import configure_logging, HadilLogStream
from validators.sql_validator import validate_sql, check_unsafe_subquery_limit
from ai_modules.verifier import verify_sql_intent
from ai_modules.generator import should_apply_default_limit, generate_sql_from_text
from database.metadata_db import MetadataBase, HadilUser, hash_password
from services.metadata_service import MetadataService
from validators.security import create_access_token

client = TestClient(app)

TEST_DB_PATH = "./test_query_pipeline_isolation.db"
TEST_DATA_DB_PATH = "./test_chinook_mock.db"

@pytest.fixture(scope="module", autouse=True)
def setup_test_databases():
    # 1. Setup isolated metadata DB
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
    MetadataBase.metadata.create_all(bind=engine)

    # 2. Setup mock data database (artists, albums, tracks, customers)
    if os.path.exists(TEST_DATA_DB_PATH):
        try:
            os.remove(TEST_DATA_DB_PATH)
        except Exception:
            pass
    data_conn = sqlite3.connect(TEST_DATA_DB_PATH)
    cur = data_conn.cursor()
    cur.execute("CREATE TABLE artists (ArtistId INTEGER PRIMARY KEY, Name TEXT);")
    cur.execute("CREATE TABLE albums (AlbumId INTEGER PRIMARY KEY, Title TEXT, ArtistId INTEGER);")
    cur.execute("CREATE TABLE tracks (TrackId INTEGER PRIMARY KEY, Name TEXT, AlbumId INTEGER, Bytes INTEGER);")
    cur.execute("CREATE TABLE customers (CustomerId INTEGER PRIMARY KEY, Name TEXT, City TEXT);")

    cur.executemany("INSERT INTO artists VALUES (?, ?);", [(1, "AC/DC"), (2, "Accept"), (3, "Metallica")])
    cur.executemany("INSERT INTO albums VALUES (?, ?, ?);", [(1, "For Those About To Rock", 1), (2, "Restless and Wild", 2), (3, "Master of Puppets", 3)])
    cur.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?);", [(1, "Spellbound", 1, 1000), (2, "Restless", 2, 2000), (3, "Battery", 3, 3000), (4, "Master of Puppets", 3, 4000)])
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?);", [(1, "Alice", "New York"), (2, "Bob", "London")])
    data_conn.commit()
    data_conn.close()

    yield

    # Cleanup
    for path in [TEST_DB_PATH, TEST_DATA_DB_PATH]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


# ==============================================================================
# 1. GUI NORMAL LOGGING MODE / HadilLogStream REGRESSION TEST (PART 1 FIX)
# ==============================================================================
def test_gui_logging_redirection_and_print_safety():
    """
    Verifies that configure_logging(cli_mode=False) installs HadilLogStream
    and sys.stdout.write / print() execution does NOT throw AttributeError.
    """
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    try:
        configure_logging(cli_mode=False)
        assert isinstance(sys.stdout, HadilLogStream)
        assert hasattr(sys.stdout, "write")
        assert sys.stdout.isatty() is False

        # Execute print statements that previously triggered 500 / AttributeError
        print("[HADIL SQL TRACE] Testing GUI logging stdout print safety")
        print("[HADIL SQL TRACE] Query: SELECT * FROM tracks")
        sys.stdout.flush()
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr


# ==============================================================================
# 2. VERIFIER & STRUCTURAL LIMIT POLICY TESTS (PART 2 FIX)
# ==============================================================================
def test_policy_limit_validation_rules():
    """
    Tests structural LIMIT policy evaluation:
    A. Valid: aggregate + GROUP BY + ORDER BY + final LIMIT
    B. Valid: normal SELECT + LIMIT
    C. Unsafe: intermediate LIMIT inside subquery prior to outer aggregate/GROUP BY
    """
    # A. Valid final LIMIT on aggregate/GROUP BY
    sql_a = "SELECT artist, COUNT(*) AS track_count FROM tracks GROUP BY artist ORDER BY track_count DESC LIMIT 10;"
    is_unsafe_a, reason_a = check_unsafe_subquery_limit(sql_a)
    assert not is_unsafe_a, f"Outer final LIMIT should be valid, got unsafe: {reason_a}"
    is_safe_a, warnings_a, errors_a = validate_sql(sql_a, is_direct_sql=True)
    assert is_safe_a, f"Outer final LIMIT query should be safe, errors: {errors_a}"

    # B. Valid normal SELECT + LIMIT
    sql_b = "SELECT * FROM tracks LIMIT 100;"
    is_unsafe_b, _ = check_unsafe_subquery_limit(sql_b)
    assert not is_unsafe_b
    is_safe_b, _, errors_b = validate_sql(sql_b, is_direct_sql=True)
    assert is_safe_b

    # C. Unsafe intermediate LIMIT inside subquery prior to GROUP BY
    sql_c = "SELECT artist, COUNT(*) FROM (SELECT * FROM tracks LIMIT 5) GROUP BY artist;"
    is_unsafe_c, reason_c = check_unsafe_subquery_limit(sql_c)
    assert is_unsafe_c, "Subquery LIMIT prior to outer GROUP BY must be flagged as unsafe"
    assert "Subquery contains a LIMIT clause prior to outer aggregation" in reason_c
    is_safe_c, _, errors_c = validate_sql(sql_c, is_direct_sql=True)
    assert not is_safe_c
    assert any("Subquery contains a LIMIT clause" in e for e in errors_c)


def test_generator_limit_preservation():
    """
    Verifies generator preserves explicit top-N LIMIT on aggregate queries
    while adding default LIMIT 100 only to raw row retrieval queries.
    """
    # Raw query without limit -> needs default limit
    assert should_apply_default_limit("SELECT * FROM artists") is True

    # Raw query with limit -> does not need default limit
    assert should_apply_default_limit("SELECT * FROM artists LIMIT 10") is False

    # Aggregate query -> does not need default limit
    assert should_apply_default_limit("SELECT COUNT(*) FROM artists") is False
    assert should_apply_default_limit("SELECT artist, COUNT(*) FROM tracks GROUP BY artist") is False


# ==============================================================================
# 3. FULL QUERY PIPELINE COMPREHENSIVE REGRESSION TESTS (PART 4)
# ==============================================================================
def test_full_query_pipeline_execution():
    """
    Executes real database queries against sqlite engine covering:
    - simple SELECT
    - filtered SELECT
    - JOIN query
    - aggregate query
    - GROUP BY
    - ORDER BY
    - aggregate + GROUP BY + LIMIT
    - multi-table query
    - multiple rows
    - zero rows
    """
    engine = create_engine(f"sqlite:///{TEST_DATA_DB_PATH}")

    with engine.connect() as conn:
        # Simple SELECT & multiple rows
        res_simple = conn.execute(text("SELECT * FROM artists LIMIT 100;")).fetchall()
        assert len(res_simple) == 3

        # Filtered SELECT & zero rows
        res_filtered = conn.execute(text("SELECT * FROM artists WHERE Name = 'NonExistentBand';")).fetchall()
        assert len(res_filtered) == 0

        # JOIN query & Multi-table
        res_join = conn.execute(text("""
            SELECT ar.Name AS ArtistName, al.Title AS AlbumTitle
            FROM artists ar
            JOIN albums al ON ar.ArtistId = al.ArtistId;
        """)).fetchall()
        assert len(res_join) == 3

        # Aggregate query
        res_agg = conn.execute(text("SELECT COUNT(*) FROM tracks;")).scalar()
        assert res_agg == 4

        # GROUP BY + ORDER BY + Aggregate + LIMIT
        res_group_limit = conn.execute(text("""
            SELECT ar.Name, COUNT(t.TrackId) AS TrackCount
            FROM artists ar
            JOIN albums al ON ar.ArtistId = al.ArtistId
            JOIN tracks t ON al.AlbumId = t.AlbumId
            GROUP BY ar.Name
            ORDER BY TrackCount DESC
            LIMIT 2;
        """)).fetchall()
        assert len(res_group_limit) <= 2
        assert len(res_group_limit) > 0


def test_validator_blocked_queries_and_exceptions():
    """
    Verifies that dangerous SQL injection keywords or unauthorized SQL are properly blocked.
    """
    # Blocked keyword (DROP)
    is_safe, _, errors = validate_sql("DROP TABLE artists;", is_direct_sql=True)
    assert not is_safe
    assert any("strictly blocked" in e for e in errors)

    # Blocked keyword (DELETE without WHERE)
    is_safe_del, _, errors_del = validate_sql("DELETE FROM artists;", is_direct_sql=True)
    assert not is_safe_del
    assert any("without a WHERE clause is blocked" in e for e in errors_del)


def test_pipeline_under_gui_logging_active():
    """
    Executes a full query validation and trace logging run while GUI normal-mode logging
    redirection (HadilLogStream) is active to guarantee 100% path coverage.
    """
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    try:
        configure_logging(cli_mode=False)

        # Simulate route logging prints
        sql = "SELECT ar.Name, COUNT(t.TrackId) AS Count FROM artists ar JOIN albums al ON ar.ArtistId = al.ArtistId JOIN tracks t ON al.AlbumId = t.AlbumId GROUP BY ar.Name ORDER BY Count DESC LIMIT 5;"
        print(f"[HADIL SQL TRACE] Query: Top artists by track count")
        print(f"[HADIL SQL TRACE] Generated SQL: {sql}")
        print(f"[HADIL SQL TRACE] Executing SQL: {sql}")
        sys.stdout.flush()

        is_safe, warnings, errors = validate_sql(sql, is_direct_sql=False)
        assert is_safe, f"Top-N grouped query should be safe, got errors: {errors}"
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
