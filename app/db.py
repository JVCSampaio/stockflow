import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents >= 0),
    reorder_point INTEGER NOT NULL CHECK(reorder_point >= 0),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0 AND quantity <= 1000000000),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    kind TEXT NOT NULL CHECK(kind IN ('in','out')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents >= 0),
    balance_after INTEGER NOT NULL CHECK(balance_after >= 0),
    note TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_movements_product ON movements(product_id,id);
PRAGMA user_version = 1;
"""


def utc_now():
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path, seed=True):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
            raise RuntimeError("Banco de dados incompatível; restaure uma cópia compatível.")
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        if seed and not db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
            examples = [
                ("MON-24", "Monitor IPS 24 polegadas", "Hardware", 84990, 5, 12),
                ("TEC-USB", "Teclado USB compacto", "Periféricos", 8990, 10, 4),
                ("MOU-WL", "Mouse sem fio", "Periféricos", 5990, 10, 28),
                ("CAB-CAT6", "Cabo de rede CAT6 · 2m", "Infraestrutura", 1890, 20, 14),
                ("RES-A4", "Resma A4 · 500 folhas", "Papelaria", 2490, 15, 42),
                ("SSD-512", "SSD NVMe 512 GB", "Hardware", 22990, 6, 0),
            ]
            for sku, name, category, cost, point, quantity in examples:
                product_id = db.execute(
                    """INSERT INTO products
                    (sku,name,category,unit_cost_cents,reorder_point,quantity,created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (sku, name, category, cost, point, quantity, utc_now()),
                ).lastrowid
                if quantity:
                    db.execute(
                        """INSERT INTO movements
                        (product_id,kind,quantity,unit_cost_cents,balance_after,note,idempotency_key,created_at)
                        VALUES (?,'in',?,?,?,?,?,?)""",
                        (
                            product_id,
                            quantity,
                            cost,
                            quantity,
                            "Saldo inicial sintético.",
                            f"seed-{sku}",
                            utc_now(),
                        ),
                    )
