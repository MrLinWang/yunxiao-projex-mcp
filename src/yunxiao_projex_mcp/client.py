from __future__ import annotations

import json
import mimetypes
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from alibabacloud_devops20210625 import models as devops_models
from alibabacloud_devops20210625.client import Client as DevopsClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from .config import Config

_METADATA_KEYS = ("requestId", "success", "errorCode", "errorMsg", "errorMessage")
_WORKITEM_FIELDS = (
    "identifier",
    "serialNumber",
    "subject",
    "categoryIdentifier",
    "status",
    "statusIdentifier",
    "statusStageIdentifier",
    "logicalStatus",
    "assignedTo",
    "creator",
    "gmtCreate",
    "gmtModified",
    "spaceIdentifier",
    "spaceName",
    "spaceType",
    "sprintIdentifier",
    "parentIdentifier",
    "workitemTypeIdentifier",
    "updateStatusAt",
)
MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass(frozen=True)
class DownloadedFile:
    name: str
    size: int
    mime_type: str
    data: bytes


class YunxiaoError(Exception):
    """Normalized Yunxiao API or configuration error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | str | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.request_id = request_id
        parts = [str(part) for part in (status, code) if part]
        prefix = " ".join(parts)
        text = f"云效 API 错误 {prefix}: {message}" if prefix else f"云效 API 错误: {message}"
        if request_id:
            text += f" (requestId={request_id})"
        super().__init__(text)


class ProjexClient:
    def __init__(self, config: Config, sdk: DevopsClient | None = None) -> None:
        self.config = config
        self._sdk = sdk or self._build_sdk(config)
        self._runtime = util_models.RuntimeOptions(autoretry=False)

    @staticmethod
    def _build_sdk(config: Config) -> DevopsClient:
        sdk_config = open_api_models.Config(
            access_key_id=config.access_key_id,
            access_key_secret=config.access_key_secret,
        )
        sdk_config.endpoint = config.endpoint
        sdk_config.connect_timeout = 10000
        sdk_config.read_timeout = 30000
        return DevopsClient(sdk_config)

    async def _call(
        self,
        method: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = await method(*args, **kwargs)
        except Exception as exc:
            raise self._translate_exception(exc) from exc

        body = self._body(response)
        self._raise_for_body(body)
        return self._strip_metadata(body)

    @staticmethod
    def _body(response: Any) -> dict[str, Any]:
        body = getattr(response, "body", None)
        if body is None:
            return {}
        if hasattr(body, "to_map"):
            body = body.to_map()
        return dict(body or {})

    @staticmethod
    def _raise_for_body(body: Mapping[str, Any]) -> None:
        error_code = body.get("errorCode")
        if body.get("success") is False or error_code not in (None, "", "success"):
            raise YunxiaoError(
                str(body.get("errorMessage") or body.get("errorMsg") or "请求失败"),
                code=str(error_code) if error_code else None,
                request_id=body.get("requestId"),
            )

    @staticmethod
    def _strip_metadata(body: dict[str, Any]) -> dict[str, Any]:
        for key in _METADATA_KEYS:
            body.pop(key, None)
        return body

    @staticmethod
    def _translate_exception(exc: Exception) -> YunxiaoError:
        status = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        message = getattr(exc, "message", None) or str(exc)
        request_id = None
        data = getattr(exc, "data", None)
        if isinstance(data, dict):
            request_id = data.get("requestId") or data.get("RequestId")
        return YunxiaoError(
            str(message),
            status=status,
            code=str(code) if code else None,
            request_id=request_id,
        )

    def _ensure_project(
        self,
        entity: Mapping[str, Any],
        kind: str,
        identifier: str,
    ) -> None:
        space = entity.get("spaceIdentifier")
        if not space:
            raise YunxiaoError(
                f"无法确认{kind} {identifier} 的项目归属",
                code="ProjectScopeUnknown",
            )
        if space != self.config.project_id:
            raise YunxiaoError(
                f"{kind} {identifier} 不属于当前项目",
                code="ProjectScopeMismatch",
            )

    async def _fetch_workitem(self, workitem_id: str) -> dict[str, Any]:
        body = await self._call(
            self._sdk.get_work_item_info_with_options_async,
            self.config.org_id,
            workitem_id,
            {},
            self._runtime,
        )
        return body.get("workitem") or {}

    async def _ensure_workitem(self, workitem_id: str) -> dict[str, Any]:
        workitem = await self._fetch_workitem(workitem_id)
        self._ensure_project(workitem, "工作项", workitem_id)
        return workitem

    async def _fetch_sprint(self, sprint_id: str) -> dict[str, Any]:
        body = await self._call(
            self._sdk.get_sprint_info_with_options_async,
            self.config.org_id,
            sprint_id,
            {},
            self._runtime,
        )
        return body.get("sprint") or {}

    async def _ensure_sprint(self, sprint_id: str) -> dict[str, Any]:
        sprint = await self._fetch_sprint(sprint_id)
        self._ensure_project(sprint, "迭代", sprint_id)
        return sprint

    async def get_project(self) -> dict[str, Any]:
        body = await self._call(
            self._sdk.get_project_info_with_options_async,
            self.config.org_id,
            self.config.project_id,
            {},
            self._runtime,
        )
        return body.get("project") or {}

    async def list_project_members(self) -> dict[str, Any]:
        body = await self._call(
            self._sdk.list_project_members_with_options_async,
            self.config.org_id,
            self.config.project_id,
            devops_models.ListProjectMembersRequest(target_type="Space"),
            {},
            self._runtime,
        )
        members = [
            {
                "identifier": member.get("identifier"),
                "displayName": member.get("displayName")
                or member.get("nickName")
                or member.get("realName"),
                "roleName": member.get("roleName"),
                "roleId": member.get("tbRoleId"),
            }
            for member in (body.get("members") or [])
        ]
        return {"members": members}

    async def list_workitem_types(self, category: str) -> dict[str, Any]:
        body = await self._call(
            self._sdk.list_project_workitem_types_with_options_async,
            self.config.org_id,
            self.config.project_id,
            devops_models.ListProjectWorkitemTypesRequest(
                space_type="Project",
                category=category,
            ),
            {},
            self._runtime,
        )
        return {"workitem_types": body.get("workitemTypes") or []}

    async def list_workitem_fields(self, workitem_type_id: str) -> dict[str, Any]:
        body = await self._call(
            self._sdk.list_work_item_all_fields_with_options_async,
            self.config.org_id,
            devops_models.ListWorkItemAllFieldsRequest(
                space_identifier=self.config.project_id,
                space_type="Project",
                workitem_type_identifier=workitem_type_id,
            ),
            {},
            self._runtime,
        )
        return {"fields": body.get("fields") or []}

    async def list_workitem_statuses(
        self,
        category: str,
        workitem_type_id: str | None = None,
    ) -> dict[str, Any]:
        body = await self._call(
            self._sdk.list_work_item_work_flow_status_with_options_async,
            self.config.org_id,
            devops_models.ListWorkItemWorkFlowStatusRequest(
                space_identifier=self.config.project_id,
                space_type="Project",
                workitem_category_identifier=category,
                workitem_type_identifier=workitem_type_id,
            ),
            {},
            self._runtime,
        )
        return {"statuses": body.get("statuses") or []}

    async def list_workitems(
        self,
        category: str,
        *,
        subject_contains: str | None = None,
        status_ids: list[str] | None = None,
        assigned_to: str | None = None,
        sprint_id: str | None = None,
        max_results: int = 20,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= max_results <= 200:
            raise YunxiaoError("max_results 必须在 1 到 200 之间", code="InvalidParameter")
        if sprint_id:
            await self._ensure_sprint(sprint_id)

        conditions = self._build_conditions(
            subject_contains=subject_contains,
            status_ids=status_ids,
            assigned_to=assigned_to,
            sprint_id=sprint_id,
        )
        body = await self._call(
            self._sdk.list_workitems_with_options_async,
            self.config.org_id,
            devops_models.ListWorkitemsRequest(
                category=category,
                conditions=conditions,
                max_results=str(max_results),
                next_token=next_token,
                space_identifier=self.config.project_id,
                space_type="Project",
            ),
            {},
            self._runtime,
        )
        items = [
            {key: item[key] for key in _WORKITEM_FIELDS if key in item}
            for item in (body.get("workitems") or [])
        ]
        return {
            "items": items,
            "total_count": body.get("totalCount", len(items)),
            "next_token": body.get("nextToken") or None,
        }

    @staticmethod
    def _build_conditions(
        *,
        subject_contains: str | None,
        status_ids: list[str] | None,
        assigned_to: str | None,
        sprint_id: str | None,
    ) -> str | None:
        conditions: list[dict[str, Any]] = []
        if subject_contains:
            conditions.append(
                {
                    "fieldIdentifier": "subject",
                    "operator": "CONTAINS",
                    "value": [subject_contains],
                    "toValue": None,
                    "className": "string",
                    "format": "input",
                }
            )
        if status_ids:
            conditions.append(
                {
                    "fieldIdentifier": "status",
                    "operator": "CONTAINS",
                    "value": status_ids,
                    "toValue": None,
                    "className": "status",
                    "format": "list",
                }
            )
        if assigned_to:
            conditions.append(
                {
                    "fieldIdentifier": "assignedTo",
                    "operator": "CONTAINS",
                    "value": [assigned_to],
                    "toValue": None,
                    "className": "user",
                    "format": "list",
                }
            )
        if sprint_id:
            conditions.append(
                {
                    "fieldIdentifier": "sprint",
                    "operator": "CONTAINS",
                    "value": [sprint_id],
                    "toValue": None,
                    "className": "sprint",
                    "format": "list",
                }
            )
        if not conditions:
            return None
        return json.dumps({"conditionGroups": [conditions]}, ensure_ascii=False)

    async def get_workitem(self, workitem_id: str) -> dict[str, Any]:
        return await self._ensure_workitem(workitem_id)

    async def get_workitem_file(
        self,
        workitem_id: str,
        file_id: str,
    ) -> DownloadedFile:
        await self._ensure_workitem(workitem_id)
        body = await self._call(
            self._sdk.get_workitem_file_with_options_async,
            self.config.org_id,
            workitem_id,
            file_id,
            {},
            self._runtime,
        )
        file_info = body.get("workitemFile") or {}
        name = file_info.get("name") or file_id
        size = file_info.get("size")
        if isinstance(size, int) and size > MAX_FILE_SIZE:
            raise YunxiaoError("附件不能超过 10 MiB", code="FileTooLarge")
        url = file_info.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise YunxiaoError("云效未返回有效的附件下载地址", code="InvalidFileUrl")

        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
            ) as http:
                response = await http.get(url)
                response.raise_for_status()
                data = response.content
                content_type = response.headers.get("content-type", "").split(";")[0]
        except httpx.HTTPStatusError as exc:
            raise YunxiaoError(
                f"附件下载失败 (HTTP {exc.response.status_code})",
                code="FileDownloadFailed",
            ) from exc
        except httpx.HTTPError as exc:
            raise YunxiaoError("附件下载请求失败", code="FileDownloadFailed") from exc

        if len(data) > MAX_FILE_SIZE:
            raise YunxiaoError("附件不能超过 10 MiB", code="FileTooLarge")
        mime_type = (
            mimetypes.guess_type(name)[0]
            or (content_type if content_type.startswith("image/") else None)
            or "application/octet-stream"
        )
        return DownloadedFile(name, len(data), mime_type, data)

    async def list_workitem_comments(self, workitem_id: str) -> dict[str, Any]:
        await self._ensure_workitem(workitem_id)
        body = await self._call(
            self._sdk.get_workitem_comment_list_with_options_async,
            self.config.org_id,
            workitem_id,
            {},
            self._runtime,
        )
        return {"comments": body.get("commentList") or []}

    async def list_sprints(
        self,
        *,
        max_results: int = 20,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= max_results <= 200:
            raise YunxiaoError("max_results 必须在 1 到 200 之间", code="InvalidParameter")
        body = await self._call(
            self._sdk.list_sprints_with_options_async,
            self.config.org_id,
            devops_models.ListSprintsRequest(
                space_identifier=self.config.project_id,
                space_type="Project",
                max_results=max_results,
                next_token=next_token,
            ),
            {},
            self._runtime,
        )
        items = body.get("sprints") or []
        return {
            "items": items,
            "total_count": body.get("totalCount", len(items)),
            "next_token": body.get("nextToken") or None,
        }

    async def get_sprint(self, sprint_id: str) -> dict[str, Any]:
        return await self._ensure_sprint(sprint_id)

    async def create_workitem(
        self,
        category: str,
        workitem_type_id: str,
        subject: str,
        assigned_to: str,
        *,
        description: str | None = None,
        description_format: str = "MARKDOWN",
        sprint_id: str | None = None,
        parent_id: str | None = None,
        participants: list[str] | None = None,
        trackers: list[str] | None = None,
        verifier: str | None = None,
        custom_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._validate_format(description_format)
        if sprint_id:
            await self._ensure_sprint(sprint_id)
        if parent_id:
            await self._ensure_workitem(parent_id)

        field_values = [
            devops_models.CreateWorkitemRequestFieldValueList(
                field_identifier=field_identifier,
                value=value,
            )
            for field_identifier, value in (custom_fields or {}).items()
        ]
        body = await self._call(
            self._sdk.create_workitem_with_options_async,
            self.config.org_id,
            devops_models.CreateWorkitemRequest(
                assigned_to=assigned_to,
                category=category,
                description=description,
                description_format=description_format,
                field_value_list=field_values or None,
                parent=parent_id,
                participant=participants,
                space=self.config.project_id,
                space_identifier=self.config.project_id,
                space_type="Project",
                sprint=[sprint_id] if sprint_id else None,
                subject=subject,
                tracker=trackers,
                verifier=[verifier] if verifier else None,
                workitem_type=workitem_type_id,
            ),
            {},
            self._runtime,
        )
        return body.get("workitem") or body

    async def update_workitem(
        self,
        workitem_id: str,
        *,
        fields: dict[str, str] | None = None,
        description: str | None = None,
        description_format: str = "MARKDOWN",
    ) -> dict[str, Any]:
        self._validate_format(description_format)
        if not fields and description is None:
            raise YunxiaoError(
                "至少提供 fields 或 description",
                code="InvalidParameter",
            )
        if fields and "description" in fields:
            raise YunxiaoError(
                "description 请使用 description 参数更新",
                code="InvalidParameter",
            )

        await self._ensure_workitem(workitem_id)
        if fields:
            await self._validate_field_references(fields)
            await self._update_fields(workitem_id, fields)
        if description is not None:
            await self._update_property(
                workitem_id,
                property_key="description",
                property_value=description,
                field_type=description_format,
            )
        return await self.get_workitem(workitem_id)

    async def _update_fields(self, workitem_id: str, fields: dict[str, str]) -> None:
        request = devops_models.UpdateWorkitemFieldRequest(
            workitem_identifier=workitem_id,
            update_workitem_property_request=[
                devops_models.UpdateWorkitemFieldRequestUpdateWorkitemPropertyRequest(
                    field_identifier=field_identifier,
                    field_value=value,
                )
                for field_identifier, value in fields.items()
            ],
        )
        try:
            await self._call(
                self._sdk.update_workitem_field_with_options_async,
                self.config.org_id,
                request,
                {},
                self._runtime,
            )
        except YunxiaoError:
            if "status" not in fields:
                raise
            remaining = {
                key: value for key, value in fields.items() if key != "status"
            }
            if remaining:
                await self._update_fields(workitem_id, remaining)
            await self._update_property(
                workitem_id,
                property_key="status",
                property_value=fields["status"],
                field_type="status",
            )

    async def _update_property(
        self,
        workitem_id: str,
        *,
        property_key: str,
        property_value: str,
        field_type: str,
    ) -> None:
        await self._call(
            self._sdk.update_work_item_with_options_async,
            self.config.org_id,
            devops_models.UpdateWorkItemRequest(
                field_type=field_type,
                identifier=workitem_id,
                property_key=property_key,
                property_value=property_value,
            ),
            {},
            self._runtime,
        )

    async def _validate_field_references(self, fields: Mapping[str, str]) -> None:
        sprint_value = fields.get("sprint")
        if sprint_value:
            for sprint_id in self._split_values(sprint_value):
                await self._ensure_sprint(sprint_id)
        parent_value = fields.get("parent")
        if parent_value:
            await self._ensure_workitem(parent_value)

    @staticmethod
    def _split_values(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _validate_format(format_type: str) -> None:
        if format_type not in ("MARKDOWN", "RICHTEXT"):
            raise YunxiaoError(
                "format 必须是 MARKDOWN 或 RICHTEXT",
                code="InvalidParameter",
            )

    async def delete_workitem(
        self,
        workitem_id: str,
        *,
        confirm: bool,
    ) -> dict[str, Any]:
        if not confirm:
            raise YunxiaoError(
                "删除工作项需要显式传 confirm=true",
                code="ConfirmationRequired",
            )
        await self._ensure_workitem(workitem_id)
        return await self._call(
            self._sdk.delete_workitem_with_options_async,
            self.config.org_id,
            devops_models.DeleteWorkitemRequest(identifier=workitem_id),
            {},
            self._runtime,
        )

    async def create_workitem_comment(
        self,
        workitem_id: str,
        content: str,
        *,
        format_type: str = "MARKDOWN",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        self._validate_format(format_type)
        await self._ensure_workitem(workitem_id)
        return await self._call(
            self._sdk.create_workitem_comment_with_options_async,
            self.config.org_id,
            devops_models.CreateWorkitemCommentRequest(
                content=content,
                format_type=format_type,
                parent_id=parent_id,
                workitem_identifier=workitem_id,
            ),
            {},
            self._runtime,
        )

    async def update_workitem_comment(
        self,
        workitem_id: str,
        comment_id: int,
        content: str,
        *,
        format_type: str = "MARKDOWN",
    ) -> dict[str, Any]:
        self._validate_format(format_type)
        await self._ensure_workitem(workitem_id)
        return await self._call(
            self._sdk.update_workitem_comment_with_options_async,
            self.config.org_id,
            devops_models.UpdateWorkitemCommentRequest(
                comment_id=comment_id,
                content=content,
                format_type=format_type,
                workitem_identifier=workitem_id,
            ),
            {},
            self._runtime,
        )

    async def delete_workitem_comment(
        self,
        workitem_id: str,
        comment_id: int,
        *,
        confirm: bool,
    ) -> dict[str, Any]:
        if not confirm:
            raise YunxiaoError(
                "删除评论需要显式传 confirm=true",
                code="ConfirmationRequired",
            )
        await self._ensure_workitem(workitem_id)
        return await self._call(
            self._sdk.delete_workitem_comment_with_options_async,
            self.config.org_id,
            devops_models.DeleteWorkitemCommentRequest(
                comment_id=comment_id,
                identifier=workitem_id,
            ),
            {},
            self._runtime,
        )

    async def create_sprint(
        self,
        name: str,
        owner_ids: list[str],
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not owner_ids:
            raise YunxiaoError("owner_ids 至少需要一项", code="InvalidParameter")
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        if start and end and start > end:
            raise YunxiaoError(
                "start_date 不能晚于 end_date",
                code="InvalidParameter",
            )
        body = await self._call(
            self._sdk.create_sprint_with_options_async,
            self.config.org_id,
            devops_models.CreateSprintRequest(
                name=name,
                space_identifier=self.config.project_id,
                staff_ids=owner_ids,
                start_date=start_date,
                end_date=end_date,
            ),
            {},
            self._runtime,
        )
        return body.get("sprint") or body

    @staticmethod
    def _parse_date(value: str | None, field_name: str) -> date | None:
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise YunxiaoError(
                f"{field_name} 必须是 YYYY-MM-DD 格式",
                code="InvalidParameter",
            ) from exc
