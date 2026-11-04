from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENDPOINT = "devops.cn-hangzhou.aliyuncs.com"
REQUIRED_ENV = (
    "YUNXIAO_USER_ACCESS_KEY_ID",
    "YUNXIAO_USER_ACCESS_KEY_SECRET",
    "YUNXIAO_API_ORG_ID",
    "YUNXIAO_API_PROJECT_ID",
)


class ConfigError(Exception):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Config:
    org_id: str
    project_id: str
    endpoint: str
    access_key_id: str = field(repr=False)
    access_key_secret: str = field(repr=False)


def _default_env_file() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def load_config(env_file: Path | str | None = None) -> Config:
    path = Path(env_file) if env_file is not None else _default_env_file()
    if path.is_file():
        load_dotenv(path, override=False)

    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise ConfigError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return Config(
        org_id=os.environ["YUNXIAO_API_ORG_ID"],
        project_id=os.environ["YUNXIAO_API_PROJECT_ID"],
        endpoint=os.getenv("YUNXIAO_API_ENDPOINT") or DEFAULT_ENDPOINT,
        access_key_id=os.environ["YUNXIAO_USER_ACCESS_KEY_ID"],
        access_key_secret=os.environ["YUNXIAO_USER_ACCESS_KEY_SECRET"],
    )
