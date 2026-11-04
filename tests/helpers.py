from __future__ import annotations

from typing import Any

from yunxiao_projex_mcp.config import Config


def make_config() -> Config:
    return Config(
        org_id="org-1",
        project_id="project-1",
        endpoint="devops.example.com",
        access_key_id="test-ak",
        access_key_secret="test-secret",
    )


class FakeBody:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_map(self) -> dict[str, Any]:
        return dict(self._data)


class FakeResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self.body = FakeBody(data)


class FakeSdk:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.responses: dict[str, Any] = {}

    async def _respond(
        self,
        name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> FakeResponse:
        self.calls.append((name, args, kwargs))
        response = self.responses.get(name, {"success": True})
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(*args, **kwargs)
        return FakeResponse(response)

    def __getattr__(self, name: str) -> Any:
        if name.endswith("_with_options_async"):
            async def method(*args: Any, **kwargs: Any) -> FakeResponse:
                return await self._respond(name, args, kwargs)

            return method
        raise AttributeError(name)
