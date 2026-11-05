from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent

from yunxiao_projex_mcp.client import DownloadedFile, YunxiaoError
from yunxiao_projex_mcp.server import create_server


class FakeClient:
    async def get_project(self):
        return {"name": "ArchRanking"}

    async def get_workitem(self, _workitem_id):
        raise YunxiaoError("workitem not found", code="NotFound")

    async def get_workitem_file(self, _workitem_id, _file_id):
        return DownloadedFile("image.png", 3, "image/png", b"png")

    async def list_project_members(self):
        return {"members": []}

    async def list_workitem_types(self, _category):
        return {"workitem_types": []}

    async def list_workitem_fields(self, _type_id):
        return {"fields": []}

    async def list_workitem_statuses(self, _category, _type_id=None):
        return {"statuses": []}

    async def list_workitems(self, _category, **_kwargs):
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
    assert len(tools) == 18
    assert set(tools) == {
        "get_project",
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
    assert result.structuredContent == {
        "name": "image.png",
        "size": 3,
        "mimeType": "image/png",
    }
    image = result.content[1]
    assert isinstance(image, ImageContent)
    assert image.mimeType == "image/png"
    assert image.data == "cG5n"
