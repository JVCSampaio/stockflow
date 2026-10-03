import csv
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from .contracts import MetricsView, MovementList, MovementView, ProductList, ProductView
from .db import connection, initialize, utc_now
from .service import StockError, get_product, register_movement, safe_cell


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ProductCreate(Input):
    sku: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,24}$")
    name: str = Field(min_length=3, max_length=120)
    category: Literal["Hardware", "Periféricos", "Infraestrutura", "Papelaria"]
    unit_cost_cents: int = Field(ge=0, le=100000000, strict=True)
    reorder_point: int = Field(ge=0, le=1000000, strict=True)

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class MovementCreate(Input):
    product_id: int = Field(ge=1, strict=True)
    kind: Literal["in", "out"]
    quantity: int = Field(gt=0, le=1000000, strict=True)
    note: str = Field(min_length=5, max_length=500)
    idempotency_key: UUID4


def create_app(db_path=None, seed=True):
    path = str(db_path or os.getenv("APP_DB", ".data/stockflow.db"))

    @asynccontextmanager
    async def lifespan(app):
        initialize(path, seed)
        yield

    app = FastAPI(
        title="StockFlow API",
        version="1.0.0",
        lifespan=lifespan,
        description="Estoque com saldo e histórico transacionais. Projeto local com dados sintéticos.",
    )

    @app.exception_handler(StockError)
    async def stock_error(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=error.status, content={"detail": error.message})

    @app.get("/api/health")
    def health():
        with connection(path) as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok", "schema_version": 1}

    @app.get("/api/products", response_model=ProductList)
    def list_products(
        q: str = Query("", max_length=120),
        low_stock: bool = False,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        clauses, values = [], []
        if q:
            literal = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("(name LIKE ? ESCAPE '\\' OR sku LIKE ? ESCAPE '\\')")
            values.extend([f"%{literal}%", f"%{literal}%"])
        if low_stock:
            clauses.append("quantity <= reorder_point")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with connection(path) as db:
            total = db.execute("SELECT COUNT(*) FROM products" + where, values).fetchone()[0]
            rows = db.execute(
                "SELECT * FROM products" + where + " ORDER BY name,id LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return {
            "items": [dict(r) | {"low_stock": r["quantity"] <= r["reorder_point"]} for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/api/products", status_code=201, response_model=ProductView)
    def create_product(body: ProductCreate):
        try:
            with connection(path) as db:
                product_id = db.execute(
                    """INSERT INTO products
                    (sku,name,category,unit_cost_cents,reorder_point,created_at) VALUES (?,?,?,?,?,?)""",
                    (body.sku, body.name, body.category, body.unit_cost_cents, body.reorder_point, utc_now()),
                ).lastrowid
                result = get_product(db, product_id)
        except sqlite3.IntegrityError as error:
            raise HTTPException(409, "Este SKU já está cadastrado.") from error
        return result

    @app.get("/api/products/{product_id}", response_model=ProductView)
    def product_detail(product_id: int):
        with connection(path) as db:
            return get_product(db, product_id)

    @app.post("/api/movements", status_code=201, response_model=MovementView)
    def create_movement(body: MovementCreate, response: Response):
        with connection(path) as db:
            result, replayed = register_movement(
                db, body.product_id, body.kind, body.quantity, body.note, str(body.idempotency_key)
            )
        if replayed:
            response.status_code = 200
            response.headers["Idempotent-Replayed"] = "true"
        return result

    @app.get("/api/movements", response_model=MovementList)
    def list_movements(
        product_id: int | None = Query(None, ge=1),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        where = " WHERE m.product_id=?" if product_id else ""
        values = [product_id] if product_id else []
        with connection(path) as db:
            total = db.execute("SELECT COUNT(*) FROM movements m" + where, values).fetchone()[0]
            rows = db.execute(
                """SELECT m.*,p.sku,p.name FROM movements m
                JOIN products p ON p.id=m.product_id"""
                + where
                + " ORDER BY m.id DESC LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}

    @app.get("/api/metrics", response_model=MetricsView)
    def metrics():
        with connection(path) as db:
            row = db.execute("""SELECT COUNT(*) products,COALESCE(SUM(quantity),0) units,
                COALESCE(SUM(quantity*unit_cost_cents),0) value_cents,
                COALESCE(SUM(quantity<=reorder_point),0) low_stock,
                COALESCE(SUM(quantity=0),0) empty FROM products""").fetchone()
        return dict(row)

    @app.get("/api/export/{report}.csv")
    def export(report: Literal["products", "movements"]):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        with connection(path) as db:
            query = (
                "SELECT * FROM products ORDER BY id"
                if report == "products"
                else "SELECT m.*,p.sku,p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id"
            )
            cursor = db.execute(query)
            columns = [c[0] for c in cursor.description]
            writer.writerow(columns)
            for row in cursor:
                writer.writerow(
                    [
                        safe_cell(row[c]) if c in ("sku", "name", "note", "category") else row[c]
                        for c in columns
                    ]
                )
        return Response(
            output.getvalue().encode("utf-8-sig"),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report}.csv"'},
        )

    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
