"""Gera exemplos sintéticos usando a API em banco temporário."""

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

root = Path(__file__).resolve().parents[1]
output = root / "docs" / "samples"
output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temporary:
    application = create_app(Path(temporary) / "example.db")
    with TestClient(application) as client:
        for report in ["products", "movements"]:
            result = client.get(f"/api/export/{report}.csv")
            result.raise_for_status()
            (output / f"{report}.csv").write_bytes(result.content)
        (root / "docs" / "openapi.json").write_text(
            json.dumps(application.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
print("Exemplos e contrato OpenAPI gerados pela aplicação.")
