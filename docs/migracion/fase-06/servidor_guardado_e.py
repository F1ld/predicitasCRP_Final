"""Instrumentación QA de serving/worker: prohibe entrenamiento y escrituras ML."""
import importlib.abc
import runpy
import sys


def install_guard():
    class NoOffline(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"training", "management", "datasets"}:
                raise AssertionError("Serving intentó importar proceso offline")
    sys.meta_path.insert(0, NoOffline())
    import joblib
    from sklearn.pipeline import Pipeline
    def forbidden(*args, **kwargs):
        raise AssertionError("Entrenamiento/escritura ML desde serving")
    Pipeline.fit = forbidden
    joblib.dump = forbidden


def main():
    install_guard()
    if sys.argv[1:] == ["worker"]:
        runpy.run_module("app.inference_worker", run_name="__main__")
    else:
        import uvicorn
        from app.main import app, get_executor
        get_executor().command = [sys.executable, "-B", __file__, "worker"]
        uvicorn.run(app, host="127.0.0.1", port=8127, workers=1,
                    limit_concurrency=16, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
