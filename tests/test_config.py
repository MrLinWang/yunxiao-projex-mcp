from __future__ import annotations

import pytest

from yunxiao_projex_mcp.config import (
    REQUIRED_ENV,
    ConfigError,
    load_config,
)


def test_missing_config_reports_names_without_values(monkeypatch, tmp_path):
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_file=tmp_path / "missing.env")

    message = str(exc_info.value)
    assert "YUNXIAO_USER_ACCESS_KEY_ID" in message
    assert "test-secret" not in message


def test_environment_variables_override_dotenv(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "YUNXIAO_API_ORG_ID=file-org",
                "YUNXIAO_API_PROJECT_ID=file-project",
                "YUNXIAO_API_ENDPOINT=file-endpoint",
                "YUNXIAO_USER_ACCESS_KEY_ID=file-ak",
                "YUNXIAO_USER_ACCESS_KEY_SECRET=file-secret",
                "YUNXIAO_USER_NAME=file-user",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("YUNXIAO_API_ORG_ID", "process-org")
    monkeypatch.setenv("YUNXIAO_API_PROJECT_ID", "process-project")
    monkeypatch.setenv("YUNXIAO_USER_ACCESS_KEY_ID", "process-ak")
    monkeypatch.setenv("YUNXIAO_USER_ACCESS_KEY_SECRET", "process-secret")
    monkeypatch.setenv("YUNXIAO_USER_NAME", "process-user")
    monkeypatch.delenv("YUNXIAO_API_ENDPOINT", raising=False)

    config = load_config(env_file=env_file)

    assert config.org_id == "process-org"
    assert config.project_id == "process-project"
    assert config.endpoint == "file-endpoint"
    assert config.access_key_id == "process-ak"
    assert config.user_name == "process-user"


def test_optional_user_name_is_trimmed_and_blank_is_none(monkeypatch, tmp_path):
    monkeypatch.setenv("YUNXIAO_API_ORG_ID", "org")
    monkeypatch.setenv("YUNXIAO_API_PROJECT_ID", "project")
    monkeypatch.setenv("YUNXIAO_USER_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("YUNXIAO_USER_ACCESS_KEY_SECRET", "secret")
    monkeypatch.setenv("YUNXIAO_USER_NAME", "  yunxiao-bot  ")

    config = load_config(env_file=tmp_path / "missing.env")
    assert config.user_name == "yunxiao-bot"

    monkeypatch.setenv("YUNXIAO_USER_NAME", "   ")
    config = load_config(env_file=tmp_path / "missing.env")
    assert config.user_name is None
