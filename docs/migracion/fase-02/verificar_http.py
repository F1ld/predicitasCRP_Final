"""Lecturas HTTP del stack Compose aislado; no login/escrituras sobre su BD."""
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

HERE = Path(__file__).resolve().parent


def main():
    target = HERE / "http_stack.json"
    if target.exists():
        raise SystemExit("No sobrescribir evidencia")
    checks = []
    for url, expected, marker in (
        ("http://127.0.0.1:18000/health", 200, None),
        ("http://127.0.0.1:18000/docs", 200, "Swagger UI"),
        ("http://127.0.0.1:18000/citas", 401, None),
        ("http://127.0.0.1:15173/", 200, "/src/main.tsx"),
        ("http://127.0.0.1:15173/src/main.tsx", 200, "App"),
        ("http://127.0.0.1:15173/citas", 200, "/src/main.tsx"),
    ):
        try:
            response = urlopen(url, timeout=20)
        except HTTPError as error:
            response = error
        body = response.read().decode("utf-8")
        ok = response.status == expected and (marker is None or marker in body)
        checks.append({"url": url, "status": response.status, "expected_status": expected, "marker_found": marker is None or marker in body, "passed": ok})
    with urlopen("http://127.0.0.1:18000/openapi.json", timeout=20) as response:
        api = json.load(response)
    expected_api = json.loads((HERE / "smoke_antes.json").read_text(encoding="utf-8"))["openapi"]
    result = {"checks": checks, "http_openapi_matches_before": api == expected_api, "writes_performed": False, "browser_visual_certified": False}
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert all(x["passed"] for x in checks) and result["http_openapi_matches_before"]
    print("HTTP: health/docs, autorización, frontend, módulo principal y deep link correctos; OpenAPI idéntico.")


if __name__ == "__main__":
    main()
