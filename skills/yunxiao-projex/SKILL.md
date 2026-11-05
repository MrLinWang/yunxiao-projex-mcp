---
name: yunxiao-projex
description: Read and modify Alibaba Cloud Yunxiao Projex work items, comments, and sprints; read project members and download authenticated attachments through the aliyun-yunxiao-projex MCP. Use for 云效 or Projex project status, backlog triage, work item updates, and screenshots embedded in descriptions; not for unrelated Alibaba Cloud services.
---

# Yunxiao Projex

通过 `aliyun-yunxiao-projex` MCP 管理云效 Projex。工具通常以
`mcp__aliyun_yunxiao_projex__*` 命名；以实际暴露的工具名为准。

## 固定项目

- 服务由 `YUNXIAO_API_PROJECT_ID` 固定到单一项目。不要向工具传项目 ID，也不要把其他项目的数据混入结果。
- 首次操作先调用 `get_project` 确认项目，再按用户要求读取或修改。
- 工具不可用或缺少环境变量时，说明需要配置 MCP；不要绕过 MCP 手工拼接云效 OpenAPI 请求。

## 读取与汇总

- `list_workitems` 每次只接受一个 `category`；汇总项目时分别查询 `Req`、`Bug` 和 `Task`。
- `serialNumber`（例如 `PYNW-5`）适合展示；工具参数需要时使用 `identifier`。
- 判断“最近更新”时使用 `gmtModified`，不要只看创建时间。需要确认内容变化时读取 `get_workitem` 和 `list_workitem_comments`。
- 查询负责人、状态或迭代前，先用 `list_project_members`、`list_workitem_statuses`、`list_sprints` 解析用户给出的名称。

## 描述中的附件

- 图片和附件位于 `document` 的 HTML/JSONML 中。从 URL 的 `fileIdentifier` 提取文件 ID，再调用
  `get_workitem_file(workitem_id=<工作项 identifier>, file_id=<fileIdentifier>)`。
- 不要直接请求 `devops.aliyun.com/projex/api/workitem/file/url?...`；该地址需要认证，会返回 401。
- 图片工具结果可直接查看并分析；非图片附件返回 Base64 嵌入资源，最大 10 MiB。

## 写入

- 创建工作项前依次查询 `list_workitem_types`、`list_workitem_fields` 和
  `list_workitem_statuses`。`assigned_to`、参与人、验证人使用成员账号 ID。
- 自定义字段（例如 `priority`）通过 `custom_fields` 传选项 identifier，不传显示文本。`description` 使用单独的
  `description` 参数，不要放进 `fields`。
- 更新状态时使用状态 identifier；更新后用 `get_workitem` 验证结果。
- 创建评论默认使用 Markdown。只有回复已有评论时才传 `parent_id`。
- 只有用户明确要求删除时才调用删除工具并传 `confirm=true`。删除工作项后索引可能延迟刷新。
- 云效没有删除迭代接口；创建迭代前向用户确认名称、负责人和日期，避免不可撤销的误建。

## Bot 边界

当前 Bot 是“开发机器人”，不应尝试修改项目配置或成员。附件上传、工作项关联、工作项动态、
工时/预估、项目创建/删除、迭代修改/删除、代码库和流水线均不在本 MCP 范围内。
