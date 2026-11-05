from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from yunxiao_projex_mcp.client import ProjexClient, YunxiaoError
from yunxiao_projex_mcp.config import load_config

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def require_live_tests():
    if os.getenv("YUNXIAO_LIVE_TESTS") != "1":
        pytest.skip("set YUNXIAO_LIVE_TESTS=1 to run live tests")


@pytest.fixture
def client() -> ProjexClient:
    return ProjexClient(load_config())


@pytest.mark.anyio
async def test_live_project_reads(client: ProjexClient):
    project = await client.get_project()
    assert project["name"] == "ArchRanking"

    members = await client.list_project_members()
    assert any(member["displayName"] == "yunxiao-bot" for member in members["members"])

    types = await client.list_workitem_types("Req")
    assert types["workitem_types"]
    workitem_type = next(
        item for item in types["workitem_types"] if item.get("defaultType")
    )

    fields = await client.list_workitem_fields(workitem_type["identifier"])
    assert any(field["identifier"] == "priority" for field in fields["fields"])

    statuses = await client.list_workitem_statuses("Req", workitem_type["identifier"])
    assert statuses["statuses"]

    workitems = await client.list_workitems("Req", max_results=5)
    assert workitems["items"] == []
    assert workitems["total_count"] == 0

    sprints = await client.list_sprints(max_results=5)
    assert sprints["items"] == []


@pytest.mark.anyio
async def test_live_foreign_resources_are_rejected(client: ProjexClient):
    foreign_workitem = os.getenv(
        "YUNXIAO_TEST_FOREIGN_WORKITEM_ID",
        "c97144734b1817bb0a1a5851f4",
    )
    foreign_sprint = os.getenv(
        "YUNXIAO_TEST_FOREIGN_SPRINT_ID",
        "e223cfdf7c68ab3ffd4ce3c44e",
    )

    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.get_workitem(foreign_workitem)
    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.get_sprint(foreign_sprint)


@pytest.mark.anyio
async def test_live_stdio_entrypoint():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "yunxiao_projex_mcp"],
        env=dict(os.environ),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 18

            result = await session.call_tool("get_project", {})

    assert result.isError is False
    assert "ArchRanking" in result.content[0].text


@pytest.mark.live_write
@pytest.mark.anyio
async def test_live_workitem_write_lifecycle(client: ProjexClient):
    if os.getenv("YUNXIAO_LIVE_WRITE_TESTS") != "1":
        pytest.skip("set YUNXIAO_LIVE_WRITE_TESTS=1 to run the write probe")

    created_id: str | None = None
    subject = f"__mcp_probe__{int(time.time())}"
    try:
        members = await client.list_project_members()
        bot = next(
            member
            for member in members["members"]
            if member["displayName"] == "yunxiao-bot"
        )
        types = await client.list_workitem_types("Req")
        workitem_type = next(
            item for item in types["workitem_types"] if item.get("defaultType")
        )
        fields = await client.list_workitem_fields(workitem_type["identifier"])
        priority = next(
            field for field in fields["fields"] if field["identifier"] == "priority"
        )
        default_priority = priority.get("defaultValue") or priority["options"][0][
            "identifier"
        ]

        created = await client.create_workitem(
            "Req",
            workitem_type["identifier"],
            subject,
            bot["identifier"],
            description="MCP write probe",
            custom_fields={"priority": default_priority},
        )
        created_id = created.get("identifier")
        assert created_id, created

        fetched = await client.get_workitem(created_id)
        assert fetched["subject"] == subject

        statuses = await client.list_workitem_statuses(
            "Req",
            workitem_type["identifier"],
        )
        status = next(
            (item for item in statuses["statuses"] if item["name"] == "开发中"),
            statuses["statuses"][0],
        )
        updated = await client.update_workitem(
            created_id,
            fields={"status": status["identifier"]},
            description="MCP write probe updated",
        )
        assert updated["subject"] == subject

        listed = await client.list_workitems(
            "Req",
            subject_contains=subject,
            status_ids=[status["identifier"], "100005"],
            max_results=20,
        )
        assert any(item["identifier"] == created_id for item in listed["items"])

        await client.create_workitem_comment(created_id, "MCP probe comment")
        comments = await client.list_workitem_comments(created_id)
        comment = next(
            item
            for item in comments["comments"]
            if item["content"] == "MCP probe comment"
        )
        comment_id = int(comment["id"])
        await client.update_workitem_comment(
            created_id,
            comment_id,
            "MCP probe comment updated",
        )
        updated_comments = await client.list_workitem_comments(created_id)
        assert any(
            item["content"] == "MCP probe comment updated"
            for item in updated_comments["comments"]
        )
        await client.delete_workitem_comment(created_id, comment_id, confirm=True)
        deleted_id = created_id
        await client.delete_workitem(created_id, confirm=True)
        created_id = None

        deadline = time.monotonic() + 20
        while True:
            remaining = await client.list_workitems(
                "Req",
                subject_contains=subject,
                max_results=20,
            )
            if all(item["identifier"] != deleted_id for item in remaining["items"]):
                break
            if time.monotonic() > deadline:
                pytest.fail(f"deleted workitem {deleted_id} is still listed")
            await asyncio.sleep(2)
    finally:
        if created_id:
            try:
                await client.delete_workitem(created_id, confirm=True)
            except Exception as exc:
                print(f"cleanup failed for {created_id}: {exc}")
