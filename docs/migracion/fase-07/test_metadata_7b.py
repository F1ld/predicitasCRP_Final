"""Validación HTTP metadata sin BD ni modelo; ejecución stdlib unittest."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

import httpx
from app.core.errores import MotorIANoDisponible
from app.modules.ia.motor_http import MotorHTTP, ROTULO


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads((ROOT / "apps/ia/manifests/legacy-approved.json").read_text())["dataset"]
        block = dict(umbral=0.45, f1_score=0.9, precision=0.9, recall=0.9, roc_auc=0.9, pr_auc=0.9,
                     matriz_confusion=dict(tn=80, fp=2, fn=2, tp=18))
        self.metrics = dict(version_modelo="v1", algoritmo="LightGBM", semilla=42,
            fecha_entrenamiento="2026-11-07T12:00:00+00:00", es_simulacion=True, rotulo_etico=ROTULO,
            umbral_alto=0.45, umbral_medio=0.3, cumple_meta_f1_82=True, metricas_test=block,
            metricas_val=block, metricas_baseline_test=block, auditoria_equidad={}, importancia_global_variables=[])

    def motor(self, payload):
        motor = MotorHTTP("http://ia.test", "clave-test", transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=payload)))
        self.addCleanup(motor.close)
        return motor

    def test_dataset_legacy(self):
        ds = self.motor(self.dataset).dataset()
        self.assertEqual((ds.train_size, ds.val_size, ds.test_size), (700, 150, 150))
        self.assertEqual(ds.tasa_no_show_global, 0.205)

    def test_dataset_training(self):
        self.dataset.update(proposito="TRAINING_RUN", fuente="SINTETICO_GENERADO", linaje_completo=True,
                            fecha_corte="2026-10-29", sha256_raw="a" * 64)
        for split in self.dataset["particiones"].values():
            split.update(sha256="a" * 64, sha256_ids="b" * 64)
        self.assertEqual(self.motor(self.dataset).dataset().total_historicas, 1000)

    def test_dataset_rechaza_incoherencias(self):
        for mutation in (lambda p: p.update(total_historicas=1001),
                lambda p: p["particiones"]["train"].update(no_show=999),
                lambda p: p.update(linaje_completo=True), lambda p: p.update(extra="no"),
                lambda p: p.update(sha256_raw="a" * 64)):
            data = copy.deepcopy(self.dataset)
            mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(MotorIANoDisponible):
                self.motor(data).dataset()

    def test_metricas(self):
        self.assertEqual(self.motor(self.metrics).metricas().metricas_test.f1_score, 0.9)

    def test_metricas_rechaza_incoherencias(self):
        for mutation in (lambda p: p.update(cumple_meta_f1_82=False),
                lambda p: p["metricas_test"].update(f1_score=1.1),
                lambda p: p.update(fecha_entrenamiento="no-fecha"),
                lambda p: p.update(extra="no"), lambda p: p.update(es_simulacion=False)):
            data = copy.deepcopy(self.metrics)
            mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(MotorIANoDisponible):
                self.motor(data).metricas()


if __name__ == "__main__":
    unittest.main(verbosity=2)
