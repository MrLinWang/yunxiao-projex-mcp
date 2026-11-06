# 云效 Projex 项目管理 MCP

<!-- mcp-name: io.github.MrLinWang/aliyun-yunxiao-projex-mcp -->

[![PyPI](https://img.shields.io/pypi/v/yunxiao-projex-mcp.svg)](https://pypi.org/project/yunxiao-projex-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An MCP server for Alibaba Cloud Yunxiao (阿里云云效) Projex project management. It exposes work items, sprints, comments, members, current-user identity, project metadata and authenticated file downloads as MCP tools over stdio.

基于阿里云云效 Projex OpenAPI 的 MCP 服务。使用 `YUNXIAO_USER_*` Bot Key，所有工具固定作用于 `YUNXIAO_API_PROJECT_ID` 指定的项目，无法访问其他项目。

## 安装

从 PyPI 运行，无需本地克隆：

```bash
uvx yunxiao-projex-mcp
```

或安装到本地环境：

```bash
uv tool install yunxiao-projex-mcp
```

本地开发：

```bash
uv sync --all-extras
```

## 配置

支持以下环境变量：

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `YUNXIAO_USER_ACCESS_KEY_ID` | 是 | 云效 Bot AccessKey ID |
| `YUNXIAO_USER_ACCESS_KEY_SECRET` | 是 | 云效 Bot AccessKey Secret |
| `YUNXIAO_USER_NAME` | 否 | 当前 AccessKey 用户的云效显示名（如 `yunxiao-bot`）；设置后严格校验，省略时自动识别 |
| `YUNXIAO_API_ORG_ID` | 是 | 云效组织 ID |
| `YUNXIAO_API_PROJECT_ID` | 是 | 云效 Projex 项目 ID |
| `YUNXIAO_API_ENDPOINT` | 否 | 默认 `devops.cn-hangzhou.aliyuncs.com` |

标准 `mcpServers` 配置（Magpie / Claude Desktop / Cursor 等通用）：

```json
{
  "mcpServers": {
    "aliyun-yunxiao-projex": {
      "command": "uvx",
      "args": ["yunxiao-projex-mcp"],
      "env": {
        "YUNXIAO_USER_ACCESS_KEY_ID": "your-access-key-id",
        "YUNXIAO_USER_ACCESS_KEY_SECRET": "your-access-key-secret",
        "YUNXIAO_USER_NAME": "yunxiao-bot",
        "YUNXIAO_API_ORG_ID": "your-organization-id",
        "YUNXIAO_API_PROJECT_ID": "your-project-id",
        "YUNXIAO_API_ENDPOINT": "devops.cn-hangzhou.aliyuncs.com"
      }
    }
  }
}
```

`YUNXIAO_API_ENDPOINT` 可省略，省略时使用默认值；`YUNXIAO_USER_NAME` 也可省略，MCP 会通过当前 AccessKey 自动识别。
如果设置 `YUNXIAO_USER_NAME`，值必须与当前 AccessKey 用户在云效的显示名完全一致（不是 AccessKey ID，也不是 `aliyun_ram:...` 完整 username）。
多个 Agent 要区分身份时，必须各自使用独立的 AccessKey；共享同一个 AccessKey 会被视为同一个用户。

### 本地 `.env`

从源码运行时，可在项目根目录放置 `.env`：

```dotenv
YUNXIAO_API_ORG_ID=...
YUNXIAO_API_PROJECT_ID=...
YUNXIAO_API_ENDPOINT=devops.cn-hangzhou.aliyuncs.com
YUNXIAO_USER_ACCESS_KEY_ID=...
YUNXIAO_USER_ACCESS_KEY_SECRET=...
YUNXIAO_USER_NAME=yunxiao-bot
```

建议执行 `chmod 600 .env`，并确保 `.env` 不被提交到版本库。

## 接入 Codex

```bash
codex mcp add aliyun-yunxiao-projex \
  --env YUNXIAO_API_ORG_ID=... \
  --env YUNXIAO_API_PROJECT_ID=... \
  --env YUNXIAO_USER_ACCESS_KEY_ID=... \
  --env YUNXIAO_USER_ACCESS_KEY_SECRET=... \
  --env YUNXIAO_USER_NAME=yunxiao-bot \
  -- uvx yunxiao-projex-mcp
codex mcp list
```

等价的 `~/.codex/config.toml` 配置：

```toml
[mcp_servers.aliyun-yunxiao-projex]
command = "uvx"
args = ["yunxiao-projex-mcp"]

[mcp_servers.aliyun-yunxiao-projex.env]
YUNXIAO_API_ORG_ID = "..."
YUNXIAO_API_PROJECT_ID = "..."
YUNXIAO_USER_ACCESS_KEY_ID = "..."
YUNXIAO_USER_ACCESS_KEY_SECRET = "..."
YUNXIAO_USER_NAME = "yunxiao-bot"
```

## 接入 Magpie

该服务已发布到官方 MCP Registry，名称为 `io.github.MrLinWang/aliyun-yunxiao-projex-mcp`。在 Magpie 的 Discover 中搜索 `yunxiao`、`projex`、`aliyun` 或 `mcp` 即可找到，安装时按提示填写环境变量。

也可以直接编辑 Magpie 的 MCP 配置，使用上面的 `mcpServers` JSON 片段。

## 配套 Skill

仓库中的 `skills/yunxiao-projex/` 是配合本 MCP 使用的 Agent Skill，包含查询、写入、工作项生命周期状态同步、自身负责人识别和附件下载约定。
在仓库根目录执行以下命令，链接到 Codex 技能目录，后续 `git pull` 会自动同步。
如果目标位置已有实体目录，先移走，避免在其中生成嵌套链接：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -sfn "$PWD/skills/yunxiao-projex" "${CODEX_HOME:-$HOME/.codex}/skills/yunxiao-projex"
```

该 Skill 依赖已配置的 `aliyun-yunxiao-projex` MCP（若注册为其他名称，工具前缀会随之变化），
不会另行保存或读取云效凭据。
新增或修改 MCP 工具、参数或权限边界时，应同步更新该 Skill，并运行：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  skills/yunxiao-projex
```

## 工具

只读：`get_project`、`get_current_user`、`list_project_members`、`list_workitem_types`、`list_workitem_fields`、`list_workitem_statuses`、`list_workitems`、`get_workitem`、`get_workitem_file`、`list_workitem_comments`、`list_sprints`、`get_sprint`。

写入：`create_workitem`、`update_workitem`、`create_workitem_comment`、`update_workitem_comment`、`create_sprint`。

删除：`delete_workitem`、`delete_workitem_comment`，均要求 `confirm=true`。

## 使用约定

- `assigned_to`、`owner_ids`、`participants`、`trackers`、`verifier` 使用项目成员的账号 ID，可通过 `list_project_members` 获取。
- 判断工作项负责人是否为自己时，调用 `get_current_user` 获取当前用户的 `identifier`，或直接使用 `list_workitems` 的 `assigned_to_me=true`；`list_workitems`/`get_workitem` 返回的 `isMine` 为 `true`/`false`。`isMine` 为 `null` 表示未配置 `YUNXIAO_USER_NAME` 且自动识别失败，可调用 `get_current_user` 查看原因。
- `YUNXIAO_USER_NAME` 只用于识别当前用户，不能直接传给 `assigned_to`；`assigned_to` 仍使用成员 identifier。
- 提交 PR 后，Skill 会把实际 PR 链接写回对应云效工作项的评论；已有交付评论时优先更新，不能只写在最终答复里。
- 创建工作项前先查 `list_workitem_types`、`list_workitem_fields` 和 `list_workitem_statuses`；必填自定义字段（例如 `priority`）通过 `custom_fields` 传入选项 ID。
- 实现或修复已绑定的工作项时，Skill 会先读取当前状态流并按阶段推进：开工进入进行中，交付进入验证态，验收后再关闭；只读查询不改状态。
- `list_project_members` 内部固定使用 `targetType=Space`。
- 描述和评论默认使用 Markdown；日期使用 `YYYY-MM-DD`。
- `get_workitem_file` 使用 Bot Key 认证获取下载地址并下载内容。传入工作项 identifier（`workitem_id`）及描述等富文本图片 URL 中的 `fileIdentifier`（`file_id`）；PNG、JPEG、GIF、WebP 以图片内容返回，其他文件以 Base64 嵌入资源返回，最大 10 MiB。
- 客户端只读取 `structuredContent`、不渲染 MCP 图片块时，给 `get_workitem_file` 传 `save_to`（目录或完整文件名）将附件保存到本地；返回 JSON 中的 `path` 可直接用于 `view_image` 等本地查看工具。
- 删除评论和删除工作项会先校验资源属于当前项目，再执行删除；工作项删除为异步生效，列表索引可能需要数秒刷新。
- `create_workitem_comment` 默认创建顶级评论，回复评论时才需要传 `parent_id`。

## 权限限制

- 当前 Bot 角色为“开发机器人”，修改项目字段、管理项目成员会返回 403。
- 不包含工时/预估、附件上传、工作项关联、工作项动态、项目创建/删除、迭代修改/删除。
- 代码库与流水线不在本服务范围内。

## 测试

```bash
.venv/bin/python -m pytest -m "not live"
YUNXIAO_LIVE_TESTS=1 .venv/bin/python -m pytest -m "live and not live_write"
YUNXIAO_LIVE_TESTS=1 YUNXIAO_LIVE_WRITE_TESTS=1 .venv/bin/python -m pytest -m live_write
```

写入测试会创建 `__mcp_probe__` 临时工作项并在结束时删除；`create_sprint` 不做线上写入测试，因为云效未提供删除迭代接口。

## 许可证

[MIT](LICENSE)
