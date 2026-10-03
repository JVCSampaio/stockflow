"""Movimentos transacionais: saldo e histórico são gravados juntos."""

from .db import utc_now


class StockError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def get_product(db, product_id):
    row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if row is None:
        raise StockError(404, "Produto não encontrado.")
    result = dict(row)
    result["low_stock"] = result["quantity"] <= result["reorder_point"]
    return result


def register_movement(db, product_id, kind, quantity, note, key):
    # Reserva a escrita antes de verificar chave e saldo: elimina a janela entre leitura e atualização.
    db.execute("BEGIN IMMEDIATE")
    previous = db.execute("SELECT * FROM movements WHERE idempotency_key=?", (key,)).fetchone()
    if previous:
        payload = (product_id, kind, quantity, note)
        original = (previous["product_id"], previous["kind"], previous["quantity"], previous["note"])
        if payload != original:
            raise StockError(409, "Esta chave de operação já foi usada com dados diferentes.")
        return dict(previous), True
    product = get_product(db, product_id)
    after = product["quantity"] + (quantity if kind == "in" else -quantity)
    if after < 0:
        raise StockError(409, f"Saldo insuficiente: {product['quantity']} unidade(s) disponível(is).")
    if after > 1000000000:
        raise StockError(409, "O movimento ultrapassa o limite de saldo.")
    db.execute("UPDATE products SET quantity=? WHERE id=?", (after, product_id))
    movement_id = db.execute(
        """INSERT INTO movements
        (product_id,kind,quantity,unit_cost_cents,balance_after,note,idempotency_key,created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (product_id, kind, quantity, product["unit_cost_cents"], after, note, key, utc_now()),
    ).lastrowid
    result = dict(db.execute("SELECT * FROM movements WHERE id=?", (movement_id,)).fetchone())
    return result, False


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
