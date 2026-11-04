from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .client import ProjexClient, YunxiaoError
from .config import ConfigError, load_config

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")]
MaxResults = Annotated[int, Field(ge=1, le=200)]
Category = Literal["Req", "Bug", "Task"]
Format = Literal["MARKDOWN", "RICHTEXT"]

READ = ToolAnnotations(readOnlyHint=True)
CREATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
UPDATE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True)
DELETE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)

INSTRUCTIONS = (
    "云效 Projex 项目管理 MCP。所有操作固定作用于 .env 中 "
    "YUNXIAO_API_PROJECT_ID 指定的项目。创建或更新工作项前，先调用 "
    "list_workitem_types、list_workitem_fields、list_workitem_statuses "
    "和 list_project_members 获取类型、必填字段、状态和账号 ID。删除操作必须显式传 "
    "confirm=true。"
)


async def _run(
    method: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    try:
        return await method(*args, **kwargs)
    except YunxiaoError as exc:
        raise ToolError(str(exc)) from exc


def create_server(client: ProjexClient) -> FastMCP:
    server = FastMCP("yunxiao-projex", instructions=INSTRUCTIONS)

    @server.tool(
        name="get_project",
        description="获取当前配置项目的基本信息。",
        annotations=READ,
    )
    async def get_project() -> dict[str, Any]:
        return await _run(client.get_project)

    @server.tool(
        name="list_project_members",
        description="列出当前项目成员及其角色，返回可用于 assigned_to 的账号 ID。",
        annotations=READ,
    )
    async def list_project_members() -> dict[str, Any]:
        return await _run(client.list_project_members)

    @server.tool(
        name="list_workitem_types",
        description="列出当前项目指定大类（Req/Bug/Task）下的工作项类型。",
        annotations=READ,
    )
    async def list_workitem_types(category: Category) -> dict[str, Any]:
        return await _run(client.list_workitem_types, category)

    @server.tool(
        name="list_workitem_fields",
        description="列出指定工作项类型的字段定义、是否必填及选项。",
        annotations=READ,
    )
    async def list_workitem_fields(
        workitem_type_id: Identifier,
    ) -> dict[str, Any]:
        return await _run(client.list_workitem_fields, workitem_type_id)

    @server.tool(
        name="list_workitem_statuses",
        description="列出指定工作项大类或类型的可用状态流。",
        annotations=READ,
    )
    async def list_workitem_statuses(
        category: Category,
        workitem_type_id: Identifier | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.list_workitem_statuses,
            category,
            workitem_type_id,
        )

    @server.tool(
        name="list_workitems",
        description=(
            "分页查询当前项目的工作项。可按标题、状态、负责人、迭代筛选；"
            "多个状态值按同一条件的可选值处理。"
        ),
        annotations=READ,
    )
    async def list_workitems(
        category: Category,
        subject_contains: str | None = None,
        status_ids: list[Identifier] | None = None,
        assigned_to: Identifier | None = None,
        sprint_id: Identifier | None = None,
        max_results: MaxResults = 20,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.list_workitems,
            category,
            subject_contains=subject_contains,
            status_ids=status_ids,
            assigned_to=assigned_to,
            sprint_id=sprint_id,
            max_results=max_results,
            next_token=next_token,
        )

    @server.tool(
        name="get_workitem",
        description="获取当前项目内单个工作项的完整信息。",
        annotations=READ,
    )
    async def get_workitem(workitem_id: Identifier) -> dict[str, Any]:
        return await _run(client.get_workitem, workitem_id)

    @server.tool(
        name="list_workitem_comments",
        description="列出当前项目内某个工作项的评论。",
        annotations=READ,
    )
    async def list_workitem_comments(
        workitem_id: Identifier,
    ) -> dict[str, Any]:
        return await _run(client.list_workitem_comments, workitem_id)

    @server.tool(
        name="list_sprints",
        description="分页列出当前项目的迭代。",
        annotations=READ,
    )
    async def list_sprints(
        max_results: MaxResults = 20,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.list_sprints,
            max_results=max_results,
            next_token=next_token,
        )

    @server.tool(
        name="get_sprint",
        description="获取当前项目内单个迭代的信息。",
        annotations=READ,
    )
    async def get_sprint(sprint_id: Identifier) -> dict[str, Any]:
        return await _run(client.get_sprint, sprint_id)

    @server.tool(
        name="create_workitem",
        description=(
            "在当前项目创建工作项。assigned_to 使用成员账号 ID；"
            "custom_fields 用于必填自定义字段，例如 priority。"
        ),
        annotations=CREATE,
    )
    async def create_workitem(
        category: Category,
        workitem_type_id: Identifier,
        subject: Annotated[str, Field(min_length=1)],
        assigned_to: Identifier,
        description: str | None = None,
        description_format: Format = "MARKDOWN",
        sprint_id: Identifier | None = None,
        parent_id: Identifier | None = None,
        participants: list[Identifier] | None = None,
        trackers: list[Identifier] | None = None,
        verifier: Identifier | None = None,
        custom_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.create_workitem,
            category,
            workitem_type_id,
            subject,
            assigned_to,
            description=description,
            description_format=description_format,
            sprint_id=sprint_id,
            parent_id=parent_id,
            participants=participants,
            trackers=trackers,
            verifier=verifier,
            custom_fields=custom_fields,
        )

    @server.tool(
        name="update_workitem",
        description=(
            "更新当前项目内的工作项。fields 是字段 identifier 到新值的映射，"
            "不能包含 description；description 单独使用 description 参数更新。"
        ),
        annotations=UPDATE,
    )
    async def update_workitem(
        workitem_id: Identifier,
        fields: dict[str, str] | None = None,
        description: str | None = None,
        description_format: Format = "MARKDOWN",
    ) -> dict[str, Any]:
        return await _run(
            client.update_workitem,
            workitem_id,
            fields=fields,
            description=description,
            description_format=description_format,
        )

    @server.tool(
        name="delete_workitem",
        description="删除当前项目内的工作项。必须显式传 confirm=true。",
        annotations=DELETE,
    )
    async def delete_workitem(workitem_id: Identifier, confirm: bool) -> dict[str, Any]:
        return await _run(client.delete_workitem, workitem_id, confirm=confirm)

    @server.tool(
        name="create_workitem_comment",
        description="给当前项目内的工作项添加评论，默认 Markdown 格式。",
        annotations=CREATE,
    )
    async def create_workitem_comment(
        workitem_id: Identifier,
        content: Annotated[str, Field(min_length=1)],
        format_type: Format = "MARKDOWN",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.create_workitem_comment,
            workitem_id,
            content,
            format_type=format_type,
            parent_id=parent_id,
        )

    @server.tool(
        name="update_workitem_comment",
        description="修改当前项目内工作项的一条评论。",
        annotations=UPDATE,
    )
    async def update_workitem_comment(
        workitem_id: Identifier,
        comment_id: Annotated[int, Field(ge=1)],
        content: Annotated[str, Field(min_length=1)],
        format_type: Format = "MARKDOWN",
    ) -> dict[str, Any]:
        return await _run(
            client.update_workitem_comment,
            workitem_id,
            comment_id,
            content,
            format_type=format_type,
        )

    @server.tool(
        name="delete_workitem_comment",
        description="删除当前项目内工作项的一条评论。必须显式传 confirm=true。",
        annotations=DELETE,
    )
    async def delete_workitem_comment(
        workitem_id: Identifier,
        comment_id: Annotated[int, Field(ge=1)],
        confirm: bool,
    ) -> dict[str, Any]:
        return await _run(
            client.delete_workitem_comment,
            workitem_id,
            comment_id,
            confirm=confirm,
        )

    @server.tool(
        name="create_sprint",
        description=(
            "在当前项目创建迭代。日期格式为 YYYY-MM-DD；"
            "owner_ids 使用成员账号 ID。云效没有删除迭代的接口。"
        ),
        annotations=CREATE,
    )
    async def create_sprint(
        name: Annotated[str, Field(min_length=1)],
        owner_ids: Annotated[list[Identifier], Field(min_length=1)],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        return await _run(
            client.create_sprint,
            name,
            owner_ids,
            start_date=start_date,
            end_date=end_date,
        )

    return server


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    server = create_server(ProjexClient(config))
    server.run(transport="stdio")
