from __future__ import annotations

from typing import Any

from yunxiao_projex_mcp.config import Config


def make_config(user_name: str | None = None) -> Config:
    return Config(
        org_id="org-1",
        project_id="project-1",
        endpoint="devops.example.com",
        access_key_id="test-ak",
        access_key_secret="not-a-real-secret",
        user_name=user_name,
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


def set_identity_responses(
    sdk: FakeSdk,
    *,
    name: str = "yunxiao-bot",
    username: str = "aliyun_ram:yunxiao-bot",
    user_id: int = 1,
    account_id: str = "user-1",
    project_member_id: str = "user-1",
    display_name: str = "yunxiao-bot",
) -> None:
    sdk.responses["get_user_info_with_options_async"] = {
        "success": True,
        "result": {"id": user_id, "name": name, "username": username},
    }
    sdk.responses["list_organization_members_with_options_async"] = {
        "success": True,
        "members": [
            {
                "accountId": account_id,
                "organizationMemberName": name,
                "state": "normal",
            }
        ],
    }
    sdk.responses["list_project_members_with_options_async"] = {
        "success": True,
        "members": [
            {"identifier": project_member_id, "displayName": display_name}
        ],
    }
