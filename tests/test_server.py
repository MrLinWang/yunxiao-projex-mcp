from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent

from yunxiao_projex_mcp.client import DownloadedFile, YunxiaoError
from yunxiao_projex_mcp.server import create_server


class FakeClient:
    def __init__(self, file: DownloadedFile | None = None):
        self.file = file or DownloadedFile("image.png", 3, "image/png", b"png")
        self.list_workitems_kwargs = None

    async def get_project(self):
        return {"name": "ArchRanking"}

    async def get_current_user(self):
        return {
            "username": "aliyun_ram:yunxiao-bot",
            "displayName": "yunxiao-bot",
            "userId": 1,
            "identifier": "user-1",
            "configuredName": "yunxiao-bot",
            "configMatched": True,
        }

    async def get_workitem(self, _workitem_id):
        raise YunxiaoError("workitem not found", code="NotFound")

    async def get_workitem_file(self, _workitem_id, _file_id):
        return self.file

    async def list_project_members(self):
        return {"members": []}

    async def list_workitem_types(self, _category):
        return {"workitem_types": []}

    async def list_workitem_fields(self, _type_id):
        return {"fields": []}

    async def list_workitem_statuses(self, _category, _type_id=None):
        return {"statuses": []}

    async def list_workitems(self, _category, **kwargs):
        self.list_workitems_kwargs = kwargs
        return {"items": [], "total_count": 0, "next_token": None}

    async def list_workitem_comments(self, _workitem_id):
        return {"comments": []}

    async def list_sprints(self, **_kwargs):
        return {"items": [], "total_count": 0, "next_token": None}

    async def get_sprint(self, _sprint_id):
        return {"identifier": _sprint_id}

    async def create_workitem(self, *_args, **_kwargs):
        return {"identifier": "w-1"}

    async def update_workitem(self, _workitem_id, **_kwargs):
        return {"identifier": _workitem_id}

    async def delete_workitem(self, _workitem_id, **_kwargs):
        return {"deleteFlag": True}

    async def create_workitem_comment(self, _workitem_id, _content, **_kwargs):
        return {"success": True}

    async def update_workitem_comment(self, _workitem_id, _comment_id, _content, **_kwargs):
        return {"success": True}

    async def delete_workitem_comment(self, _workitem_id, _comment_id, **_kwargs):
        return {"deleteFlag": True}

    async def create_sprint(self, _name, _owner_ids, **_kwargs):
        return {"identifier": "s-1"}


@pytest.mark.anyio
async def test_server_registers_expected_tools_and_annotations():
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.list_tools()

    tools = {tool.name: tool for tool in result.tools}
    assert len(tools) == 19
    assert set(tools) == {
        "get_project",
        "get_current_user",
        "list_project_members",
        "list_workitem_types",
        "list_workitem_fields",
        "list_workitem_statuses",
        "list_workitems",
        "get_workitem",
        "get_workitem_file",
        "list_workitem_comments",
        "list_sprints",
        "get_sprint",
        "create_workitem",
        "update_workitem",
        "delete_workitem",
        "create_workitem_comment",
        "update_workitem_comment",
        "delete_workitem_comment",
        "create_sprint",
    }
    assert tools["get_project"].annotations.readOnlyHint is True
    assert tools["get_current_user"].annotations.readOnlyHint is True
    assert tools["delete_workitem"].annotations.destructiveHint is True
    assert tools["create_workitem"].annotations.destructiveHint is False


@pytest.mark.anyio
async def test_server_returns_structured_tool_result():
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("get_project", {})

    assert result.isError is False
    assert result.structuredContent == {"name": "ArchRanking"}
    assert json.loads(result.content[0].text) == {"name": "ArchRanking"}


@pytest.mark.anyio
async def test_server_returns_current_user_identity():
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("get_current_user", {})

    assert result.isError is False
    assert result.structuredContent["displayName"] == "yunxiao-bot"
    assert result.structuredContent["identifier"] == "user-1"


@pytest.mark.anyio
async def test_server_forwards_assigned_to_me():
    client = FakeClient()
    server = create_server(client)

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "list_workitems",
            {"category": "Req", "assigned_to_me": True},
        )

    assert result.isError is False
    assert client.list_workitems_kwargs["assigned_to_me"] is True


@pytest.mark.anyio
async def test_server_returns_is_mine_in_workitem_items():
    class MineClient(FakeClient):
        async def list_workitems(self, _category, **kwargs):
            self.list_workitems_kwargs = kwargs
            return {
                "items": [
                    {
                        "identifier": "w-1",
                        "assignedTo": "user-1",
                        "isMine": True,
                    }
                ],
                "total_count": 1,
                "next_token": None,
            }

    server = create_server(MineClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("list_workitems", {"category": "Req"})

    assert result.isError is False
    assert result.structuredContent["items"][0]["isMine"] is True


@pytest.mark.anyio
async def test_server_converts_yunxiao_error_to_tool_error():
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("get_workitem", {"workitem_id": "w-1"})

    assert result.isError is True
    assert "workitem not found" in result.content[0].text


@pytest.mark.anyio
async def test_server_returns_downloaded_image_content():
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "get_workitem_file",
            {"workitem_id": "w-1", "file_id": "file-1"},
        )

    assert result.isError is False
    assert result.structuredContent is None
    image = result.content[1]
    assert isinstance(image, ImageContent)
    assert image.mimeType == "image/png"
    assert image.data == "cG5n"


@pytest.mark.anyio
async def test_server_saves_downloaded_file_to_path(tmp_path):
    server = create_server(FakeClient())
    target = tmp_path / "shot.png"

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "get_workitem_file",
            {"workitem_id": "w-1", "file_id": "file-1", "save_to": str(target)},
        )

    assert result.isError is False
    assert target.read_bytes() == b"png"
    assert result.structuredContent == {
        "name": "image.png",
        "size": 3,
        "mimeType": "image/png",
        "path": str(target.resolve()),
    }
    assert json.loads(result.content[0].text)["path"] == str(target.resolve())
    assert len(result.content) == 1


@pytest.mark.anyio
async def test_server_saves_downloaded_file_into_directory(tmp_path):
    server = create_server(FakeClient())

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "get_workitem_file",
            {"workitem_id": "w-1", "file_id": "file-1", "save_to": str(tmp_path)},
        )

    assert result.isError is False
    assert (tmp_path / "image.png").read_bytes() == b"png"
    assert result.structuredContent["path"] == str((tmp_path / "image.png").resolve())


@pytest.mark.anyio
async def test_server_returns_non_image_as_embedded_resource():
    file = DownloadedFile("report.pdf", 4, "application/pdf", b"%PDF")
    server = create_server(FakeClient(file))

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "get_workitem_file",
            {"workitem_id": "w-1", "file_id": "file-1"},
        )

    assert result.isError is False
    assert result.structuredContent is None
    assert result.content[1].type == "resource"
