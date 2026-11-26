"""Database migration tests -- structured logging, steps, retries, and failures."""

from __future__ import annotations

import logging
import pytest

from stepdoc import step

log = logging.getLogger("migrations")


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

MIGRATIONS = [
    ("001", "Create users table", "CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT now())"),
    ("002", "Create orders table", "CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id), total NUMERIC(10,2), status TEXT, created_at TIMESTAMPTZ DEFAULT now())"),
    ("003", "Add index on orders.created_at", "CREATE INDEX idx_orders_created ON orders(created_at)"),
    ("004", "Create products table", "CREATE TABLE products (id SERIAL PRIMARY KEY, sku TEXT UNIQUE, name TEXT, price NUMERIC(10,2))"),
    ("005", "Add order_items junction", "CREATE TABLE order_items (order_id INT REFERENCES orders(id), product_id INT REFERENCES products(id), qty INT, PRIMARY KEY(order_id, product_id))"),
]

COLUMN_MIGRATIONS = [
    ("006", "Add users.phone_number", "ALTER TABLE users ADD COLUMN phone_number TEXT"),
    ("007", "Add users.is_verified", "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT false"),
    ("008", "Add orders.shipped_at", "ALTER TABLE orders ADD COLUMN shipped_at TIMESTAMPTZ"),
]


# ---------------------------------------------------------------------------
# Core migration tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version,description,sql",
    MIGRATIONS,
    ids=[m[0] for m in MIGRATIONS],
)
def test_migration_apply_forward(version, description, sql):
    """Apply a single forward migration and verify schema state."""
    db = log.getChild("database")
    mgr = log.getChild("migration")

    with step(f"Apply migration {version}: {description}"):
        mgr.info("Loading migration file", extra={"version": version, "file": f"V{version}__{description.replace(' ', '_').lower()}.sql"})
        mgr.debug("SQL preview", extra={"sql": sql[:80]})
        with step("Acquire advisory lock"):
            db.info("SELECT pg_advisory_lock(12345)")
            db.debug("Lock acquired", extra={"lock_id": 12345})

    with step("Execute migration in transaction"):
        db.info("BEGIN")
        db.debug("Executing DDL", extra={"statement": sql})
        db.info("DDL executed successfully")
        with step("Update schema_version table"):
            db.info("INSERT INTO schema_version (version, description, applied_at) VALUES (%s, %s, now())", extra={"version": version})
            db.info("COMMIT")

    with step("Verify post-migration schema"):
        mgr.info("Running schema introspection")
        db.debug("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        table_count = int(version)
        mgr.info("Tables found", extra={"count": table_count})
        with step("Release advisory lock"):
            db.info("SELECT pg_advisory_unlock(12345)")
            db.debug("Lock released")

    assert int(version) > 0


def test_migration_full_chain():
    """Apply all migrations in sequence, verifying cumulative state."""
    db = log.getChild("database")
    mgr = log.getChild("migration")

    with step("Initialize empty database"):
        db.info("CREATE DATABASE migration_test TEMPLATE template0")
        db.debug("Database created", extra={"data": {"name": "migration_test", "encoding": "UTF8"}})
        with step("Install extensions"):
            db.info("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            db.info("CREATE EXTENSION IF NOT EXISTS uuid-ossp")

    with step(f"Apply {len(MIGRATIONS)} migrations sequentially"):
        for version, description, sql in MIGRATIONS:
            mgr.info(f"Applying V{version}: {description}")
            db.debug("BEGIN; " + sql[:60] + "...; COMMIT")
            mgr.debug("Migration applied", extra={"version": version, "duration_ms": 12 + int(version) * 3})

    with step("Final schema verification"):
        expected_tables = ["users", "orders", "products", "order_items"]
        for table in expected_tables:
            db.info(f"Checking table '{table}'", extra={"exists": True})
        mgr.info("Schema version", extra={"current": "005", "total_migrations": 5})
        with step("Verify foreign key constraints"):
            db.debug("FK: orders.user_id -> users.id OK")
            db.debug("FK: order_items.order_id -> orders.id OK")
            db.debug("FK: order_items.product_id -> products.id OK")

    assert True


def test_migration_idempotency():
    """Verify running the same migration twice is safe."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Apply migration 001 -- first run"):
        mgr.info("Applying V001: Create users table")
        db.info("CREATE TABLE IF NOT EXISTS users ...")
        db.debug("Table created", extra={"new": True})

    with step("Apply migration 001 -- second run"):
        mgr.info("Applying V001 again")
        db.info("CREATE TABLE IF NOT EXISTS users ...")
        db.debug("Table already exists -- no-op", extra={"new": False})
        with step("Verify schema unchanged"):
            db.info("Schema diff: none")

    with step("Validate schema_version table"):
        mgr.info("SELECT COUNT(*) FROM schema_version WHERE version = '001'")
        mgr.debug("Count", extra={"count": 1, "note": "no duplicate entry"})

    assert True


def test_migration_rollback():
    """Apply and then rollback a migration."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Apply migration 004: Create products table"):
        db.info("BEGIN")
        db.debug("CREATE TABLE products (...)")
        db.info("COMMIT")
        mgr.info("Migration 004 applied")

    with step("Rollback migration 004"):
        mgr.info("Loading rollback script", extra={"file": "V004__rollback.sql"})
        db.info("BEGIN")
        db.debug("DROP TABLE IF EXISTS products CASCADE")
        db.info("COMMIT")
        with step("Update schema_version"):
            db.info("DELETE FROM schema_version WHERE version = '004'")
            mgr.info("Rollback complete", extra={"version_now": "003"})

    with step("Verify products table removed"):
        db.info("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'products')")
        db.debug("Result: false (table removed)")
        with step("Verify dependent objects also removed"):
            db.debug("order_items FK to products: removed via CASCADE")

    assert True


@pytest.mark.parametrize(
    "version,description,sql",
    COLUMN_MIGRATIONS,
    ids=[m[0] for m in COLUMN_MIGRATIONS],
)
def test_migration_add_column(version, description, sql):
    """Add a new column via ALTER TABLE migration."""
    db = log.getChild("database")
    mgr = log.getChild("migration")

    with step(f"Apply column migration {version}"):
        mgr.info("Migration", extra={"version": version, "description": description})
        db.info("BEGIN")
        db.debug("Executing", extra={"sql": sql})
        db.info("Column added successfully")
        db.info("COMMIT")

    with step("Verify column exists"):
        col_name = sql.split("ADD COLUMN ")[-1].split(" ")[0]
        db.info(f"SELECT column_name FROM information_schema.columns WHERE column_name = '{col_name}'")
        db.debug("Column found", extra={"column": col_name, "table": sql.split("ALTER TABLE ")[-1].split(" ")[0]})
        with step("Check default value"):
            if "DEFAULT" in sql:
                default = sql.split("DEFAULT ")[-1]
                db.debug("Default value", extra={"default": default})

    assert True


def test_migration_concurrent_safety():
    """Two migration runners must not conflict."""
    runner1 = log.getChild("runner_1")
    runner2 = log.getChild("runner_2")
    lock = log.getChild("lock")

    with step("Runner 1 acquires advisory lock"):
        runner1.info("Attempting pg_advisory_lock(99999)")
        lock.info("Lock granted to runner 1", extra={"lock_id": 99999})

    with step("Runner 2 attempts to acquire same lock"):
        runner2.info("Attempting pg_advisory_lock(99999)")
        runner2.warning("Lock held by another session -- waiting")
        lock.debug("Lock queue", extra={"waiting": 1, "holder": "runner_1"})

    with step("Runner 1 completes and releases lock"):
        runner1.info("Migration applied, releasing lock")
        lock.info("Lock released by runner 1")
        with step("Runner 2 acquires lock"):
            runner2.info("Lock acquired after wait", extra={"wait_ms": 1200})
            runner2.info("Checking if migration already applied")
            runner2.debug("Migration already at target version -- skipping")

    with step("Both runners complete safely"):
        runner1.info("Runner 1 finished")
        runner2.info("Runner 2 finished (no-op)")
        lock.info("No deadlocks detected")

    assert True


def test_migration_data_migration():
    """Run a data migration that transforms existing rows."""
    db = log.getChild("database")
    data = log.getChild("data_migration")

    with step("Analyze current data"):
        data.info("SELECT COUNT(*) FROM users WHERE phone_number IS NULL")
        data.debug("Result", extra={"null_count": 4521, "total_rows": 5000})

    with step("Execute data transformation"):
        data.info("Backfilling phone_number from legacy_contacts table")
        db.info("BEGIN")
        db.debug("UPDATE users SET phone_number = lc.phone FROM legacy_contacts lc WHERE users.id = lc.user_id")
        data.info("Rows updated", extra={"updated": 3890, "skipped": 631, "duration_ms": 850})
        db.info("COMMIT")

    with step("Verify data integrity post-migration"):
        data.info("SELECT COUNT(*) FROM users WHERE phone_number IS NOT NULL")
        data.debug("Non-null count", extra={"count": 3890})
        with step("Check for format violations"):
            data.info("SELECT COUNT(*) FROM users WHERE phone_number !~ '^\\+[0-9]{10,15}$'")
            data.debug("Invalid format count", extra={"count": 0})

    assert True


# ---------------------------------------------------------------------------
# Flaky / retry tests
# ---------------------------------------------------------------------------


def test_migration_lock_timeout_retry(flaky_service):
    """Advisory lock times out on first attempt, succeeds on retry."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Attempt to acquire migration lock"):
        mgr.info("SELECT pg_try_advisory_lock(12345)")
        try:
            flaky_service("migration_lock_timeout")
        except ConnectionError:
            mgr.error("Lock acquisition failed -- another migration in progress", extra={"lock_id": 12345})
            with step("Wait and retry"):
                mgr.info("Sleeping 2s before retry")
                result = flaky_service("migration_lock_timeout")
                mgr.info("Lock acquired on retry", extra={"result": result})

    with step("Apply migration with acquired lock"):
        db.info("BEGIN; CREATE TABLE temp_test (...); COMMIT")
        mgr.debug("Migration applied", extra={"version": "009"})
        with step("Release lock"):
            db.info("SELECT pg_advisory_unlock(12345)")

    assert True


def test_migration_connection_drop_retry(flaky_service):
    """Database connection drops mid-migration, reconnect and retry."""
    db = log.getChild("database")
    mgr = log.getChild("migration")

    with step("Begin migration transaction"):
        db.info("Checking connection health")
        try:
            flaky_service("migration_conn_drop")
        except ConnectionError:
            db.error("Connection reset by peer", extra={"errno": "ECONNRESET"})
            with step("Reconnect to database"):
                db.info("Establishing new connection", extra={"host": "db.internal", "port": 5432})
                result = flaky_service("migration_conn_drop")
                db.info("Reconnected", extra={"result": result})

    with step("Retry migration from scratch"):
        mgr.info("Verifying no partial state from failed attempt")
        db.debug("SELECT * FROM schema_version ORDER BY version DESC LIMIT 1")
        db.debug("Last applied version", extra={"version": "005"})
        mgr.info("Applying migration 006")
        db.info("BEGIN; ALTER TABLE users ADD COLUMN phone_number TEXT; COMMIT")
        mgr.info("Migration 006 applied successfully")

    assert True


def test_migration_replication_lag_retry(flaky_service):
    """Replica not caught up after migration, retry read."""
    db = log.getChild("primary")
    replica = log.getChild("replica")

    with step("Apply migration on primary"):
        db.info("Migration applied on primary", extra={"version": "007"})
        db.debug("WAL position", extra={"lsn": "0/1A000060"})

    with step("Verify on replica"):
        replica.info("Checking schema on replica")
        try:
            flaky_service("migration_replica_lag")
        except ConnectionError:
            replica.error("Replica not yet caught up", extra={"primary_lsn": "0/1A000060", "replica_lsn": "0/19FFF000"})
            with step("Wait for replication catch-up"):
                replica.info("Polling replication lag...")
                result = flaky_service("migration_replica_lag")
                replica.info("Replica caught up", extra={"result": result, "lag_bytes": 0})

    with step("Confirm schema consistent across nodes"):
        db.info("Primary schema version: 007")
        replica.info("Replica schema version: 007")
        replica.debug("Schema diff: none")

    assert True


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------


def test_migration_foreign_key_violation():
    """Insert violating FK constraint -- deliberately fails."""
    db = log.getChild("database")

    with step("Create parent and child tables"):
        db.info("CREATE TABLE departments (id SERIAL PRIMARY KEY, name TEXT)")
        db.info("CREATE TABLE employees (id SERIAL PRIMARY KEY, dept_id INT REFERENCES departments(id))")
        db.debug("Tables created")

    with step("Insert into child without parent"):
        db.info("INSERT INTO employees (dept_id) VALUES (999)")
        db.error("FK violation", extra={"constraint": "employees_dept_id_fkey", "detail": "Key (dept_id)=(999) is not present in table departments"})

    with step("Assert insertion succeeded"):
        inserted = False
        db.info("Checking insertion result", extra={"inserted": inserted})

    assert inserted, "Insert should have succeeded but FK constraint was violated"


def test_migration_duplicate_version_conflict():
    """Applying a migration with duplicate version number -- deliberately fails."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Apply migration V003"):
        mgr.info("Applying V003: Add index on orders.created_at")
        db.info("CREATE INDEX idx_orders_created ON orders(created_at)")
        mgr.debug("Applied", extra={"version": "003"})

    with step("Attempt to apply another V003"):
        mgr.warning("Version 003 already exists in schema_version")
        db.info("INSERT INTO schema_version (version) VALUES ('003')")
        db.error("Unique constraint violation", extra={"constraint": "schema_version_pkey"})

    with step("Assert no duplicate versions"):
        versions = ["001", "002", "003", "003"]
        unique = len(set(versions))
        total = len(versions)
        mgr.info("Version check", extra={"total": total, "unique": unique})

    assert unique == total, f"Duplicate migration versions found: {total} total vs {unique} unique"


# ---------------------------------------------------------------------------
# Schema inspection and validation
# ---------------------------------------------------------------------------


def test_migration_index_creation():
    """Create and verify database indexes."""
    db = log.getChild("database")
    idx = log.getChild("index")

    with step("Create composite index"):
        idx.info("Creating index on orders(user_id, created_at)")
        db.info("CREATE INDEX idx_orders_user_created ON orders(user_id, created_at)")
        db.debug("Index created", extra={"data": {"name": "idx_orders_user_created", "type": "btree", "columns": ["user_id", "created_at"]}})

    with step("Analyze index statistics"):
        idx.info("Running ANALYZE on orders table")
        db.debug("ANALYZE orders")
        idx.info("Index stats", extra={"size_kb": 2048, "tuples": 50000, "pages": 256})
        with step("Verify index is used by planner"):
            db.info("EXPLAIN SELECT * FROM orders WHERE user_id = 1 ORDER BY created_at")
            db.debug("Plan uses index scan", extra={"index": "idx_orders_user_created", "scan_type": "Index Scan"})

    with step("Test partial index"):
        idx.info("CREATE INDEX idx_orders_pending ON orders(status) WHERE status = 'pending'")
        db.debug("Partial index created", extra={"data": {"name": "idx_orders_pending", "predicate": "status = 'pending'"}})

    assert True


def test_migration_constraint_validation():
    """Validate CHECK and UNIQUE constraints after migration."""
    db = log.getChild("database")
    constraint = log.getChild("constraint")

    with step("Add CHECK constraint"):
        db.info("ALTER TABLE products ADD CONSTRAINT chk_price_positive CHECK (price > 0)")
        constraint.debug("Constraint added", extra={"data": {"name": "chk_price_positive", "type": "CHECK"}})

    with step("Test constraint enforcement"):
        constraint.info("INSERT INTO products (sku, name, price) VALUES ('TEST', 'Test Product', 29.99)")
        constraint.debug("Insert succeeded -- price is positive")
        with step("Attempt negative price"):
            constraint.info("INSERT INTO products (sku, name, price) VALUES ('BAD', 'Bad Product', -5.00)")
            constraint.warning("Constraint violation (simulated)", extra={"constraint": "chk_price_positive"})

    with step("Verify UNIQUE constraint on sku"):
        constraint.info("INSERT INTO products (sku, name, price) VALUES ('TEST', 'Duplicate', 19.99)")
        constraint.warning("Unique violation on sku='TEST'", extra={"constraint": "products_sku_key"})
        db.debug("Constraint correctly prevents duplicate")

    assert True


@pytest.mark.skip(reason="Partition management requires PG 12+ features not in test harness")
def test_migration_table_partitioning():
    """Create range-partitioned table."""
    db = log.getChild("database")

    with step("Create partitioned orders table"):
        db.info("CREATE TABLE orders_partitioned (...) PARTITION BY RANGE (created_at)")

    assert True


@pytest.mark.skip(reason="Materialized view refresh test requires populated data")
def test_migration_materialized_view():
    """Create and refresh a materialized view."""
    db = log.getChild("database")

    with step("CREATE MATERIALIZED VIEW monthly_sales AS ..."):
        db.info("View created")

    assert True


def test_migration_extension_install():
    """Install and verify PostgreSQL extensions."""
    db = log.getChild("database")
    ext = log.getChild("extension")

    with step("Install required extensions"):
        extensions = ["pgcrypto", "pg_trgm", "uuid-ossp", "btree_gist"]
        for e in extensions:
            ext.info(f"CREATE EXTENSION IF NOT EXISTS {e}")
            ext.debug(f"Extension '{e}' installed", extra={"version": "1.3"})

    with step("Verify extension functions available"):
        ext.info("Testing pgcrypto: SELECT gen_random_uuid()")
        ext.debug("Result", extra={"uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})
        with step("Test pg_trgm similarity"):
            ext.info("SELECT similarity('hello', 'helo')")
            ext.debug("Similarity score", extra={"score": 0.6})

    with step("List installed extensions"):
        db.info("SELECT extname, extversion FROM pg_extension")
        for e in extensions:
            db.debug(f"  {e}: installed")
        ext.info("All extensions verified", extra={"count": len(extensions)})

    assert True


def test_migration_vacuum_analyze():
    """Run VACUUM ANALYZE after bulk migration to update statistics."""
    db = log.getChild("database")
    maint = log.getChild("maintenance")

    with step("Check table bloat before vacuum"):
        maint.info("Inspecting dead tuples", extra={"table": "orders"})
        db.info("SELECT n_dead_tup, n_live_tup FROM pg_stat_user_tables WHERE relname = 'orders'")
        maint.debug("Stats", extra={"dead_tuples": 12500, "live_tuples": 50000, "bloat_pct": 25})

    with step("Run VACUUM ANALYZE"):
        db.info("VACUUM ANALYZE orders")
        maint.info("Vacuum in progress", extra={"pages_scanned": 2048, "pages_removed": 512})
        maint.debug("Vacuum complete", extra={"duration_ms": 340, "dead_tuples_removed": 12500})
        with step("Update planner statistics"):
            maint.info("Statistics refreshed", extra={"table": "orders", "columns_analyzed": 6})

    with step("Verify improved stats"):
        db.info("SELECT n_dead_tup FROM pg_stat_user_tables WHERE relname = 'orders'")
        maint.info("Post-vacuum stats", extra={"dead_tuples": 0, "live_tuples": 50000, "bloat_pct": 0})

    assert True


def test_migration_schema_dump_compare():
    """Dump schema before and after migration, compare for correctness."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Dump schema before migration"):
        db.info("pg_dump --schema-only --no-owner migration_test > before.sql")
        mgr.debug("Schema dump captured", extra={"file": "before.sql", "size_kb": 18})

    with step("Apply migration 005"):
        mgr.info("Applying V005: Add order_items junction")
        db.info("BEGIN; CREATE TABLE order_items (...); COMMIT")
        mgr.debug("Migration applied")

    with step("Dump schema after migration"):
        db.info("pg_dump --schema-only --no-owner migration_test > after.sql")
        mgr.debug("Schema dump captured", extra={"file": "after.sql", "size_kb": 22})

    with step("Compare schema diffs"):
        mgr.info("Running diff between before.sql and after.sql")
        mgr.debug("Diff result", extra={
            "added_lines": 15,
            "removed_lines": 0,
            "new_objects": ["order_items", "order_items_pkey"],
        })
        with step("Verify diff matches expected changes"):
            mgr.info("Schema diff matches migration 005 expectations")

    assert True


def test_migration_dry_run():
    """Execute migration in dry-run mode without committing."""
    mgr = log.getChild("migration")
    db = log.getChild("database")

    with step("Begin dry-run transaction"):
        db.info("BEGIN")
        mgr.info("Dry-run mode enabled -- will ROLLBACK at end")

    with step("Apply migration DDL"):
        mgr.info("Applying V006: Add users.phone_number")
        db.info("ALTER TABLE users ADD COLUMN phone_number TEXT")
        db.debug("Column added (within transaction)")
        with step("Verify column exists in transaction"):
            db.info("SELECT column_name FROM information_schema.columns WHERE column_name = 'phone_number'")
            db.debug("Column visible within transaction", extra={"found": True})

    with step("Rollback dry-run"):
        db.info("ROLLBACK")
        mgr.info("Dry-run complete -- no changes persisted")
        with step("Verify column not present after rollback"):
            db.info("SELECT column_name FROM information_schema.columns WHERE column_name = 'phone_number'")
            db.debug("Column not found (rollback successful)", extra={"found": False})

    assert True
