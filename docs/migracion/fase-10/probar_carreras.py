"""Adapta el arnés D al ciclo de vida del backend de fase 10."""
from contextlib import nullcontext
from pathlib import Path
import sys

source = Path(sys.argv.pop(1)).read_text(encoding="utf-8")
substitutions = (
    ('not (url.hostname or "").startswith("predicitas-fase4-") or url.path != "/predicitas_fase4_test"',
     'url.hostname != "db" or url.path != "/predicitas_f10_test"', 1),
    ("with TestClient(app) as client:", "with nullcontext(TestClient(app)) as client:", 2),
    ('if __name__ == "__main__":\n    main()',
     'if __name__ == "__main__":\n    with TestClient(app):\n        main()', 1),
)
for old, new, count in substitutions:
    if source.count(old) != count:
        raise RuntimeError("Cambió el arnés de referencia")
    source = source.replace(old, new)
exec(compile(source, "probar_concurrencia_d.py", "exec"), {"__name__": "__main__", "nullcontext": nullcontext})
