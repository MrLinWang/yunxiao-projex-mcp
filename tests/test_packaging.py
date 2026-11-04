from __future__ import annotations

import json
import tomllib
from pathlib import Path

from yunxiao_projex_mcp.config import REQUIRED_ENV

ROOT = Path(__file__).resolve().parents[1]


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _server() -> dict:
    return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))


def test_server_json_matches_package_metadata() -> None:
    project = _project()
    server = _server()

    assert server["name"] == "io.github.MrLinWang/aliyun-yunxiao-projex-mcp"
    assert server["version"] == project["version"]

    (package,) = server["packages"]
    assert package["registryType"] == "pypi"
    assert package["identifier"] == project["name"]
    assert package["version"] == project["version"]
    assert package["transport"] == {"type": "stdio"}


def test_readme_declares_registry_name_and_install_command() -> None:
    project = _project()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    name = project["name"]

    assert f"mcp-name: {_server()['name']}" in readme
    assert f'"args": ["{name}"]' in readme
    assert f"uvx {name}" in readme


def test_registry_env_covers_required_config() -> None:
    (package,) = _server()["packages"]
    required = {item["name"] for item in package["environmentVariables"] if item["isRequired"]}

    assert set(REQUIRED_ENV) <= required
