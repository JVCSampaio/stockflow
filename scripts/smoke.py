"""Verifica uma instância HTTP já iniciada (usado no CI do container)."""

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8080")
base = parser.parse_args().base_url.rstrip("/")


def get(path):
    with urlopen(base + path, timeout=3) as response:
        return response.read()


for attempt in range(40):
    try:
        health = json.loads(get("/api/health"))
        if health["status"] == "ok":
            break
    except HTTPError, URLError, TimeoutError:
        time.sleep(0.25)
else:
    raise RuntimeError("API não ficou pronta.")
assert b'<div id="root"></div>' in get("/")
assert json.loads(get("/api/products"))["total"] >= 6
assert json.loads(get("/openapi.json"))["info"]["version"] == "1.0.0"
assert len(get("/api/export/products.csv")) > 100
print("OK: página React, API, OpenAPI, seed e CSV no container.")
