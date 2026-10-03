"""Minimal pytest-shim + runner（本机无 pip/pytest，仅用 stdlib 验证）。
支持本仓库测试用到的：fixture(db/generated)、pytest.raises、tmp_path、monkeypatch。
"""
import importlib.util
import os
import sys
import tempfile
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


class _Raises:
    def __init__(self, exc):
        self.exc = exc
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        if evalue is None:
            raise AssertionError(f"expected {self.exc.__name__}, nothing raised")
        self.value = evalue
        return issubclass(etype, self.exc)


class _MonkeyPatch:
    def __init__(self):
        self._stash = []

    def setenv(self, k, v):
        old = os.environ.get(k)
        self._stash.append((k, old))
        os.environ[k] = v

    def undo(self):
        for k, old in reversed(self._stash):
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
        self._stash.clear()


class _Pytest:
    raises = staticmethod(_Raises)


sys.modules.setdefault("pytest", _Pytest())


def _fresh_db_conn(tmp):
    os.environ["DATA_DIR"] = str(tmp)
    for mod in [m for m in list(sys.modules) if m.startswith("app.")]:
        del sys.modules[mod]
    from app import seed
    seed.init_db()
    from app.db import connect
    return connect()


def make_db():
    tmp = tempfile.mkdtemp()
    return _fresh_db_conn(Path(tmp))


def make_generated(db):
    from app.modules import clean_generate
    clean_generate.generate_week(db, 1, days=7)
    db.commit()
    return db


FIXTURES = {"db": make_db, "generated": lambda: make_generated(make_db())}


def run_file(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = []
    for name in sorted(dir(mod)):
        if not name.startswith("test_"):
            continue
        fn = getattr(mod, name)
        if not callable(fn):
            continue
        db = make_db()
        try:
            if "generated" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                gen = make_generated(db)
                fn(gen)
            elif "db" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                fn(db)
            else:
                fn()
            results.append((name, True, ""))
        except Exception:
            results.append((name, False, traceback.format_exc()))
        finally:
            db.close()
    return results


def main():
    tests_dir = BACKEND / "app" / "tests"
    all_results = []
    for f in sorted(tests_dir.glob("test_*.py")):
        all_results += [(f.name, *r) for r in run_file(f)]
    passed = sum(1 for r in all_results if r[1])
    failed = len(all_results) - passed
    for fname, name, ok, tb in all_results:
        print(f"{'PASS' if ok else 'FAIL'}  {fname}::{name}")
        if not ok:
            print(tb)
    print(f"\n{passed} passed, {failed} failed, {len(all_results)} total")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
