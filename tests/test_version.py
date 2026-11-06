"""The project version is declared in four places; they must agree."""

import json
import tomllib
from pathlib import Path

from swu.web.app import app

ROOT = Path(__file__).resolve().parents[1]


def test_versions_agree():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    openapi = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))
    expected = pyproject["project"]["version"]
    assert package["version"] == expected, "web/package.json"
    assert app.version == expected, "FastAPI app in swu/web/app.py"
    assert openapi["info"]["version"] == expected, "docs/openapi.json (re-export it)"
