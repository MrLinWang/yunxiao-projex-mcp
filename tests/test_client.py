from __future__ import annotations

import json

import httpx
import pytest

from yunxiao_projex_mcp.client import ProjexClient, YunxiaoError

from .helpers import FakeSdk, make_config


class FakeTeaError(Exception):
    status_code = 403
    code = "Operate.NoPermission"
    message = "NoPermission"
    data = {"requestId": "request-1"}


@pytest.mark.anyio
async def test_workitem_outside_project_is_rejected():
    sdk = FakeSdk()
    sdk.responses["get_work_item_info_with_options_async"] = {
        "success": True,
        "workitem": {"identifier": "w-1", "spaceIdentifier": "other-project"},
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.get_workitem("w-1")


@pytest.mark.anyio
async def test_sprint_outside_project_is_rejected():
    sdk = FakeSdk()
    sdk.responses["get_sprint_info_with_options_async"] = {
        "success": True,
        "sprint": {"identifier": "s-1", "spaceIdentifier": "other-project"},
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.get_sprint("s-1")


@pytest.mark.anyio
async def test_file_outside_project_is_rejected_before_download():
    sdk = FakeSdk()
    sdk.responses["get_work_item_info_with_options_async"] = {
        "success": True,
        "workitem": {"identifier": "w-1", "spaceIdentifier": "other-project"},
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.get_workitem_file("w-1", "file-1")

    called = [name for name, _args, _kwargs in sdk.calls]
    assert "get_workitem_file_with_options_async" not in called


@pytest.mark.anyio
async def test_file_download_uses_authenticated_metadata_and_returns_content(monkeypatch):
    sdk = FakeSdk()
    sdk.responses["get_work_item_info_with_options_async"] = {
        "success": True,
        "workitem": {"identifier": "w-1", "spaceIdentifier": "project-1"},
    }
    sdk.responses["get_workitem_file_with_options_async"] = {
        "success": True,
        "workitemFile": {
            "name": "image.png",
            "size": 3,
            "url": "https://files.example.com/signed",
        },
    }
    client = ProjexClient(make_config(), sdk)

    class FakeHttp:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.urls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            self.urls.append(url)
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                headers={"content-type": "image/png"},
                content=b"png",
            )

    http = FakeHttp()
    def make_http(**kwargs):
        http.kwargs = kwargs
        return http

    monkeypatch.setattr(httpx, "AsyncClient", make_http)

    result = await client.get_workitem_file("w-1", "file-1")

    assert result.data == b"png"
    assert result.mime_type == "image/png"
    assert http.urls == ["https://files.example.com/signed"]
    assert http.kwargs == {"timeout": 30, "follow_redirects": True}


@pytest.mark.anyio
async def test_file_download_rejects_large_metadata_before_http():
    sdk = FakeSdk()
    sdk.responses["get_work_item_info_with_options_async"] = {
        "success": True,
        "workitem": {"identifier": "w-1", "spaceIdentifier": "project-1"},
    }
    sdk.responses["get_workitem_file_with_options_async"] = {
        "success": True,
        "workitemFile": {
            "name": "large.bin",
            "size": 10 * 1024 * 1024 + 1,
            "url": "https://files.example.com/signed",
        },
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="10 MiB"):
        await client.get_workitem_file("w-1", "file-1")


@pytest.mark.anyio
async def test_list_workitems_builds_conditions_and_normalizes_page():
    sdk = FakeSdk()
    sdk.responses["list_workitems_with_options_async"] = {
        "success": True,
        "workitems": [
            {
                "identifier": "w-1",
                "subject": "cpu analysis",
                "document": "large body",
            }
        ],
        "totalCount": 1,
        "nextToken": "next-1",
    }
    client = ProjexClient(make_config(), sdk)

    result = await client.list_workitems(
        "Req",
        subject_contains="cpu",
        status_ids=["1", "2"],
        assigned_to="user-1",
        max_results=50,
    )

    request = sdk.calls[-1][1][1]
    conditions = json.loads(request.conditions)
    assert request.space_identifier == "project-1"
    assert request.space_type == "Project"
    assert request.max_results == "50"
    assert conditions == {
        "conditionGroups": [
            [
                {
                    "fieldIdentifier": "subject",
                    "operator": "CONTAINS",
                    "value": ["cpu"],
                    "toValue": None,
                    "className": "string",
                    "format": "input",
                },
                {
                    "fieldIdentifier": "status",
                    "operator": "CONTAINS",
                    "value": ["1", "2"],
                    "toValue": None,
                    "className": "status",
                    "format": "list",
                },
                {
                    "fieldIdentifier": "assignedTo",
                    "operator": "CONTAINS",
                    "value": ["user-1"],
                    "toValue": None,
                    "className": "user",
                    "format": "list",
                },
            ]
        ]
    }
    assert result == {
        "items": [{"identifier": "w-1", "subject": "cpu analysis"}],
        "total_count": 1,
        "next_token": "next-1",
    }


@pytest.mark.anyio
async def test_list_workitems_rejects_invalid_page_size():
    client = ProjexClient(make_config(), FakeSdk())

    with pytest.raises(YunxiaoError, match="1 到 200"):
        await client.list_workitems("Req", max_results=0)


@pytest.mark.anyio
async def test_http_200_business_error_is_normalized():
    sdk = FakeSdk()
    sdk.responses["get_project_info_with_options_async"] = {
        "success": False,
        "errorCode": "Operate.NoPermission",
        "errorMsg": "NoPermission",
        "requestId": "request-2",
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError) as exc_info:
        await client.get_project()

    message = str(exc_info.value)
    assert "Operate.NoPermission" in message
    assert "request-2" in message


@pytest.mark.anyio
async def test_sdk_exception_is_normalized():
    sdk = FakeSdk()
    sdk.responses["get_project_info_with_options_async"] = FakeTeaError()
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError) as exc_info:
        await client.get_project()

    message = str(exc_info.value)
    assert "403" in message
    assert "Operate.NoPermission" in message
    assert "request-1" in message
    assert "test-secret" not in message


@pytest.mark.anyio
async def test_delete_requires_confirmation_before_api_call():
    sdk = FakeSdk()
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="confirm=true"):
        await client.delete_workitem("w-1", confirm=False)

    assert sdk.calls == []


@pytest.mark.anyio
async def test_update_rejects_description_in_fields():
    sdk = FakeSdk()
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="description 参数"):
        await client.update_workitem("w-1", fields={"description": "x"})

    assert sdk.calls == []


@pytest.mark.anyio
async def test_update_requires_fields_or_description():
    sdk = FakeSdk()
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="至少提供"):
        await client.update_workitem("w-1")

    assert sdk.calls == []


@pytest.mark.anyio
async def test_update_status_falls_back_to_update_work_item():
    sdk = FakeSdk()
    sdk.responses["get_work_item_info_with_options_async"] = {
        "success": True,
        "workitem": {
            "identifier": "w-1",
            "spaceIdentifier": "project-1",
            "subject": "updated",
        },
    }

    def update_fields_response(_org, request, _headers, _runtime):
        has_status = any(
            prop.field_identifier == "status"
            for prop in request.update_workitem_property_request
        )
        if has_status:
            raise FakeTeaError()
        return {"success": True}

    sdk.responses["update_workitem_field_with_options_async"] = update_fields_response
    sdk.responses["update_work_item_with_options_async"] = {"success": True}
    client = ProjexClient(make_config(), sdk)

    result = await client.update_workitem(
        "w-1",
        fields={"status": "2", "subject": "updated"},
    )

    assert result["subject"] == "updated"
    called = [name for name, _args, _kwargs in sdk.calls]
    assert "update_work_item_with_options_async" in called


@pytest.mark.anyio
async def test_create_sprint_validates_date_format_and_order():
    client = ProjexClient(make_config(), FakeSdk())

    with pytest.raises(YunxiaoError, match="YYYY-MM-DD"):
        await client.create_sprint("Sprint", ["user-1"], start_date="2026-13-01")

    with pytest.raises(YunxiaoError, match="不能晚于"):
        await client.create_sprint(
            "Sprint",
            ["user-1"],
            start_date="2026-02-02",
            end_date="2026-01-01",
        )


@pytest.mark.anyio
async def test_create_workitem_rejects_foreign_sprint_before_creation():
    sdk = FakeSdk()
    sdk.responses["get_sprint_info_with_options_async"] = {
        "success": True,
        "sprint": {"identifier": "s-1", "spaceIdentifier": "other-project"},
    }
    client = ProjexClient(make_config(), sdk)

    with pytest.raises(YunxiaoError, match="不属于当前项目"):
        await client.create_workitem(
            "Req",
            "type-1",
            "subject",
            "user-1",
            sprint_id="s-1",
        )

    called = [name for name, _args, _kwargs in sdk.calls]
    assert "create_workitem_with_options_async" not in called
