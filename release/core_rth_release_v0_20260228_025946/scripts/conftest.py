from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _purge_modules(prefixes: list[str]) -> None:
    for name in list(sys.modules.keys()):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            sys.modules.pop(name, None)


@pytest.fixture(scope="session")
def isolated_env(tmp_path_factory: pytest.TempPathFactory):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    base = tmp_path_factory.mktemp("rth_test_runtime")
    os.environ["RTH_MODEL_CONTROL_PLANE_BASE"] = str(base / "models")
    os.environ["RTH_SECRET_STORE_BASE"] = str(base / "secrets")
    os.environ["RTH_SECRET_STORE_MODE"] = "file_obfuscated"
    yield base


@pytest.fixture()
def client(isolated_env):
    _purge_modules(
        [
            "app.api.api_v1.api",
            "app.api.api_v1.endpoints",
            "app.core.secret_store",
            "app.core.model_control_plane",
            "app.core.telegram_bridge",
            "app.core.whatsapp_bridge",
            "app.core.mail_bridge",
        ]
    )
    api_mod = importlib.import_module("app.api.api_v1.api")
    app = FastAPI()
    app.include_router(api_mod.api_router, prefix="/api/v1")
    with TestClient(app) as c:
        c.post("/api/v1/models/reload", json={"reselect_path": True})
        yield c
