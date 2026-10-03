from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import connection
from app.main import create_app
from app.service import StockError, register_movement


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "test.db"
    with TestClient(create_app(path, seed=False)) as test_client:
        test_client.db_path = path
        yield test_client


def product(client, **values):
    payload = {
        "sku": "TEST-01",
        "name": "Monitor de teste",
        "category": "Hardware",
        "unit_cost_cents": 10050,
        "reorder_point": 3,
    } | values
    response = client.post("/api/products", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def move(client, product_id, kind="in", quantity=10, key=None, note="Operação de teste."):
    return client.post(
        "/api/movements",
        json={
            "product_id": product_id,
            "kind": kind,
            "quantity": quantity,
            "note": note,
            "idempotency_key": key or str(uuid4()),
        },
    )


def test_create_normalizes_sku_and_rejects_duplicate(client):
    p = product(client, sku="test-01")
    assert p["sku"] == "TEST-01"
    assert p["quantity"] == 0
    assert p["low_stock"] is True
    assert (
        client.post(
            "/api/products",
            json={
                "sku": "TEST-01",
                "name": "Duplicate",
                "category": "Hardware",
                "unit_cost_cents": 1,
                "reorder_point": 1,
            },
        ).status_code
        == 409
    )


def test_entry_exit_metrics_and_ledger(client):
    p = product(client)
    assert move(client, p["id"], quantity=10).json()["balance_after"] == 10
    assert move(client, p["id"], "out", 7).json()["balance_after"] == 3
    stored = client.get(f"/api/products/{p['id']}").json()
    assert stored["quantity"] == 3
    assert stored["low_stock"] is True
    metrics = client.get("/api/metrics").json()
    assert metrics["value_cents"] == 30150
    assert metrics["units"] == 3
    assert metrics["low_stock"] == 1
    events = client.get("/api/movements").json()["items"]
    assert sum(e["quantity"] * (1 if e["kind"] == "in" else -1) for e in events) == stored["quantity"]


def test_insufficient_stock_rolls_back_everything(client):
    p = product(client)
    move(client, p["id"], quantity=5)
    rejected = move(client, p["id"], "out", 6)
    assert rejected.status_code == 409
    assert client.get(f"/api/products/{p['id']}").json()["quantity"] == 5
    assert client.get("/api/movements").json()["total"] == 1


def test_retry_is_idempotent_and_conflicting_payload_is_rejected(client):
    p = product(client)
    key = str(uuid4())
    first = move(client, p["id"], quantity=4, key=key)
    replay = move(client, p["id"], quantity=4, key=key)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.headers["idempotent-replayed"] == "true"
    assert first.json() == replay.json()
    assert move(client, p["id"], quantity=5, key=key).status_code == 409
    assert client.get(f"/api/products/{p['id']}").json()["quantity"] == 4
    assert client.get("/api/movements").json()["total"] == 1


def test_simultaneous_exits_cannot_oversell(client):
    p = product(client)
    move(client, p["id"], quantity=10)

    def attempt():
        try:
            with connection(client.db_path) as db:
                register_movement(db, p["id"], "out", 6, "Saída concorrente.", str(uuid4()))
            return 201
        except StockError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [201, 409]
    assert client.get(f"/api/products/{p['id']}").json()["quantity"] == 4
    assert client.get("/api/movements").json()["total"] == 2


def test_simultaneous_retry_records_only_one_entry(client):
    p = product(client)
    key = str(uuid4())

    def attempt():
        with connection(client.db_path) as db:
            return register_movement(db, p["id"], "in", 6, "Entrada concorrente.", key)[1]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [False, True]
    assert client.get(f"/api/products/{p['id']}").json()["quantity"] == 6
    assert client.get("/api/movements").json()["total"] == 1


def test_validation_and_missing_product(client):
    p = product(client)
    for invalid in [0, -1, 1.5, True]:
        assert move(client, p["id"], quantity=invalid).status_code == 422
    assert move(client, 999).status_code == 404
    assert client.get("/api/products/999").status_code == 404
    assert client.get("/api/products?limit=101").status_code == 422


def test_filters_and_literal_search(client):
    p = product(client, name="Monitor 100% pronto")
    other = product(client, sku="OTHER-01", name="Teclado básico")
    move(client, other["id"], quantity=20)
    low = client.get("/api/products?low_stock=true").json()
    assert [x["id"] for x in low["items"]] == [p["id"]]
    assert client.get("/api/products", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/products", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert len(client.get("/api/products?limit=1&offset=1").json()["items"]) == 1


def test_csv_exports_and_formula_protection(client):
    p = product(client, name="=Formula demonstrativa")
    move(client, p["id"], note="=Motivo demonstrativo")
    for report in ["products", "movements"]:
        response = client.get(f"/api/export/{report}.csv")
        assert response.status_code == 200
        assert "'=Formula" in response.content.decode("utf-8-sig")
    assert "'=Motivo" in client.get("/api/export/movements.csv").content.decode("utf-8-sig")
    assert client.get("/api/export/unknown.csv").status_code == 422


def test_restart_and_seed_ledger_reconcile(tmp_path):
    path = tmp_path / "persistent.db"
    with TestClient(create_app(path)) as first:
        count = first.get("/api/metrics").json()["products"]
        p = product(first)
        move(first, p["id"], quantity=11)
    with TestClient(create_app(path)) as second:
        assert second.get("/api/metrics").json()["products"] == count + 1
        assert second.get(f"/api/products/{p['id']}").json()["quantity"] == 11
        rows = second.get("/api/products").json()["items"]
        events = second.get("/api/movements?limit=100").json()["items"]
        for row in rows:
            balance = sum(
                e["quantity"] * (1 if e["kind"] == "in" else -1)
                for e in events
                if e["product_id"] == row["id"]
            )
            assert balance == row["quantity"]


def test_unknown_schema_preserves_database(tmp_path):
    path = tmp_path / "future.db"
    with connection(path) as db:
        db.execute("PRAGMA user_version=9")
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match="incompatível"), TestClient(create_app(path)):
        pass
    assert path.read_bytes() == original
