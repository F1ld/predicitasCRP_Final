"""Autopruebas stdlib del gate D; sin importar backend/IA ni conectar a BD."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("gate_d", Path(__file__).with_name("inventariar_legacy_d.py"))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def temporary():
    preferred = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp/opencode"
    return tempfile.TemporaryDirectory(dir=preferred if preferred.is_dir() else None)


class GateTests(unittest.TestCase):
    def parse(self, code, path="apps/backend/app/modules/citas/check.py"):
        return gate.references(code, path)

    def test_absolute_and_alias(self):
        refs = self.parse("from app.modules.citas.synthetic import generar_citas as crear")
        self.assertEqual(refs[0]["module"], gate.LEGACY)
        self.assertEqual(refs[0]["symbol"], gate.SYMBOL)

    def test_relative_import(self):
        self.assertEqual(self.parse("from .synthetic import generar_citas")[0]["module"], gate.LEGACY)

    def test_module_imports(self):
        for code in ("import app.modules.citas.synthetic as s", "from app.modules.citas import synthetic as s"):
            self.assertEqual(self.parse(code)[0]["kind"], "module")

    def test_bridge_and_star(self):
        for symbol in ("generar_citas", "*"):
            self.assertEqual(self.parse("from app.modules.citas.public import " + symbol)[0]["module"], gate.PUBLIC)

    def test_unrelated_public_dto_is_not_a_generator(self):
        self.assertEqual(self.parse("from app.modules.citas.public import CitaConsulta"), [])

    def test_namespace_is_informational(self):
        refs = self.parse("from app.modules.citas import public as citas\ncitas.obtener_cita_consulta(db, 1)")
        self.assertEqual([r["kind"] for r in refs], ["namespace"])

    def test_aliased_attribute_and_getattr(self):
        for call in ("citas.generar_citas()", "getattr(citas, 'generar_citas')()"):
            refs = self.parse("from app.modules.citas import public as citas\n" + call)
            self.assertTrue(any(r["symbol"] == gate.SYMBOL for r in refs))

    def test_literal_dynamic_imports(self):
        for call in ("__import__('app.modules.citas.synthetic')", "importlib.import_module('app.modules.citas.public')"):
            self.assertEqual(self.parse(call)[0]["kind"], "dynamic-literal")

    def test_comments_and_documentation_not_executed(self):
        self.assertEqual(self.parse("# from app.modules.citas.synthetic import generar_citas\n'from app.modules.citas.synthetic import generar_citas'"), [])

    def fixture(self, root):
        for scope in gate.SCOPES:
            (root / scope).mkdir(parents=True, exist_ok=True)
        for producer in gate.PRODUCERS:
            (root / producer).parent.mkdir(parents=True, exist_ok=True)
            (root / producer).write_text("# QA producer\n", encoding="utf-8")
        return {"allowed_references": [], "producer_sha256_lf": gate.inventory(root)["producer_sha256_lf"],
                "retirement_review_approved": False}

    def test_manual_approval_required_even_without_references(self):
        with temporary() as directory:
            root = Path(directory)
            policy = self.fixture(root)
            actual = gate.inventory(root)
            self.assertTrue(gate.evaluate(actual, policy)["inventory_valid"])
            self.assertFalse(gate.evaluate(actual, policy)["retirement_allowed"])
            policy["retirement_review_approved"] = True
            self.assertTrue(gate.evaluate(actual, policy)["retirement_allowed"])

    def test_new_consumer_rejected(self):
        with temporary() as directory:
            root = Path(directory)
            policy = self.fixture(root)
            (root / "apps/backend/scripts/unexpected.py").write_text("from app.modules.citas.synthetic import generar_citas")
            result = gate.evaluate(gate.inventory(root), policy)
            self.assertFalse(result["inventory_valid"])
            self.assertEqual(len(result["unexpected_references"]), 1)

    def test_allowed_consumer_still_blocks_removal(self):
        with temporary() as directory:
            root = Path(directory)
            policy = self.fixture(root)
            (root / "apps/backend/scripts/known.py").write_text("from app.modules.citas.synthetic import generar_citas")
            actual = gate.inventory(root)
            policy["allowed_references"] = actual["references"]
            result = gate.evaluate(actual, policy)
            self.assertTrue(result["inventory_valid"])
            self.assertFalse(result["retirement_allowed"])

    def test_premature_removal_or_change_rejected(self):
        with temporary() as directory:
            root = Path(directory)
            policy = self.fixture(root)
            producer = root / gate.PRODUCERS[0]
            producer.write_text("# changed\n")
            self.assertFalse(gate.evaluate(gate.inventory(root), policy)["inventory_valid"])
            producer.unlink()  # Archivo temporal propio, nunca archivo de proyecto.
            self.assertTrue(gate.inventory(root)["errors"])

    def test_missing_scope_and_syntax_error_fail_closed(self):
        with temporary() as directory:
            root = Path(directory)
            self.assertTrue(gate.inventory(root)["errors"])
            self.fixture(root)
            (root / "apps/backend/scripts/broken.py").write_text("def incomplete(")
            self.assertEqual(gate.inventory(root)["errors"][0]["error"], "SOURCE_UNREADABLE")

    def test_lf_hash_normalization(self):
        with temporary() as directory:
            root = Path(directory)
            a, b = root / "a.py", root / "b.py"
            a.write_bytes(b"one\ntwo\n")
            b.write_bytes(b"one\r\ntwo\r\n")
            self.assertEqual(gate.fingerprint(a), gate.fingerprint(b))

    def test_removed_consumer_requires_review(self):
        policy = {"allowed_references": self.parse("from app.modules.citas.synthetic import generar_citas"),
                  "producer_sha256_lf": {}, "retirement_review_approved": False}
        result = gate.evaluate({"references": [], "errors": [], "producer_sha256_lf": {}}, policy)
        self.assertFalse(result["inventory_valid"])
        self.assertTrue(result["removed_references_requiring_policy_review"])

    def scheduled_fixture(self):
        bridge = self.parse("from app.modules.citas.synthetic import generar_citas",
                            "apps/backend/app/modules/citas/public.py")
        consumer = self.parse("from app.modules.citas.synthetic import generar_citas",
                              "apps/backend/scripts/exportar_csv.py")
        policy = {"allowed_references": bridge + consumer, "producer_sha256_lf": {},
                  "scheduled_retirement_approved": True, "scheduled_exceptions": bridge,
                  "retirement_review_approved": False}
        actual = {"references": bridge + consumer, "errors": [], "producer_sha256_lf": {}}
        return actual, policy

    def test_scheduled_approval_does_not_hide_remaining_migrations(self):
        actual, policy = self.scheduled_fixture()
        result = gate.evaluate(actual, policy)
        self.assertTrue(result["inventory_valid"])
        self.assertTrue(result["scheduled_retirement_approved"])
        self.assertFalse(result["scheduled_closure_ready"])
        self.assertEqual(len(result["remaining_migrations"]), 1)

    def test_scheduled_closure_does_not_authorize_physical_removal(self):
        actual, policy = self.scheduled_fixture()
        actual["references"] = policy["scheduled_exceptions"]
        policy["allowed_references"] = policy["scheduled_exceptions"]
        result = gate.evaluate(actual, policy)
        self.assertTrue(result["scheduled_closure_ready"])
        self.assertFalse(result["retirement_allowed"])

    def test_scheduled_closure_needs_approval_and_valid_inventory(self):
        actual, policy = self.scheduled_fixture()
        actual["references"] = []
        policy["allowed_references"] = []
        policy["scheduled_retirement_approved"] = False
        self.assertFalse(gate.evaluate(actual, policy)["scheduled_closure_ready"])
        policy["scheduled_retirement_approved"] = True
        actual["errors"] = [{"error": "SOURCE_UNREADABLE"}]
        self.assertFalse(gate.evaluate(actual, policy)["scheduled_closure_ready"])


if __name__ == "__main__":
    unittest.main()
