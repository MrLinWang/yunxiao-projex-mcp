---
name: yunxiao-projex
description: Read and modify Alibaba Cloud Yunxiao Projex work items, comments, and sprints; keep requirement, bug, and task status current from implementation through verification; identify work assigned to the current user, read project members, and download authenticated attachments through the aliyun-yunxiao-projex MCP. Use when a task may correspond to a Projex work item—especially before starting implementation and at delivery—as well as for 云效/Projex status, backlog triage, work item updates, and screenshots embedded in descriptions; not for unrelated Alibaba Cloud services.
---

# Yunxiao Projex

通过 `aliyun-yunxiao-projex` MCP 管理云效 Projex。工具通常以
`mcp__aliyun_yunxiao_projex__*` 命名；以实际暴露的工具名为准。

## 固定项目

- 服务由 `YUNXIAO_API_PROJECT_ID` 固定到单一项目。不要向工具传项目 ID，也不要把其他项目的数据混入结果。
- 首次操作先调用 `get_project` 确认项目，再按用户要求读取或修改。
- `YUNXIAO_USER_NAME` 可选：当前 AccessKey 用户的云效显示名。未设置时由 MCP 自动识别；设置后必须与 AccessKey 用户一致。它只用于识别自己，不是 `assigned_to` 参数。
- 工具不可用或缺少环境变量时，说明需要配置 MCP；不要绕过 MCP 手工拼接云效 OpenAPI 请求。

## 工作项状态同步

当本轮任务是在实现、修复或推进项目中的需求、Bug 或任务时，状态同步是工作的一部分：
**只读不改；开工进行中；交付待验证；验收才关闭。** 不要等用户提醒，也不要只在最终答复里口头说明。
只查看、汇总或讨论工作项时，不改变状态。

> 状态流不是固定契约：不同工作项类型、不同项目配置可能不同，也可能在会话期间变化。
> 下文提到的「开发中」「待验收」「已修复」等只是语义示例，实际操作前必须先读取当前状态流。

### 1. 每次流转前：读取当前状态流

- 每次准备进入进行中、交付验证或关闭工作项时，先调用
  `list_workitem_statuses(category=<Req|Bug|Task>, workitem_type_id=<当前工作项类型>)`，
  读取当前可用的状态名称、identifier、`workflowStageName`，并结合 `get_workitem` 确认当前状态。
- 如果返回中没有阶段字段，退回按状态名称和状态描述判断语义，不要因此沿用旧名称或旧 identifier。
- 按阶段语义选择目标，而不是只匹配字面名称：
  - 确认阶段 ≈ 未开始
  - 处理/开发阶段 ≈ 进行中
  - 验证阶段 ≈ 待验证/待验收
  - 正常结束 ≈ 已完成/已关闭
  - 异常结束 ≈ 已取消
- 再结合状态名称、当前状态和用户意图选定具体状态。没有完全对应的语义时，选择最接近且不误导的状态，
  并在评论或最终答复中说明。
- 更新时传本次查询返回的 status identifier；不要复用上次查询、其他工作项类型或其他项目的结果。

### 2. 绑定工作项

- 用户给出 `serialNumber`、标题或 identifier 时，先 `get_workitem` 读取当前状态。
- 会话中已经明确过唯一工作项时，后续“改一下/修复/继续/实现”等指令默认继续关联它；用户明确说与它无关时除外。
- 用户只描述功能或问题时，用 `list_workitems` 的 `subject_contains` 搜索；必要时叠加状态、负责人、迭代缩小范围。
- 只有唯一匹配且属于本轮范围时才自动更新。多个候选或无法确认时，不做状态写入，在答复中说明并请用户确认。
- 找不到对应工作项时，不要为了更新状态而擅自创建；可以建议用户创建。

### 3. 开工：进入进行中

开始实际修改代码、排查 Bug 或推进任务之前，先按上面的方法查询当前状态流，再选择进行中状态：

- **需求**：优先选择开发阶段中表示实际开发的状态（例如「开发中」）；没有开发阶段时，选处理阶段中表示进行中的状态。
  只做分析或方案时，选处理阶段的状态（例如「处理中」）。
- **Bug / 任务**：选择处理阶段中表示正在处理的状态（例如「处理中」）。
- 当前状态已经与目标语义一致时跳过更新；如果当前还在更早的进行中阶段（例如需求从「处理中」进入实际开发），
  按当前状态流推进到更具体的进行中状态。已经在验证态但用户要求继续修改时，先切回进行中/开发中（若允许），
  不要一边改代码一边保持待验收。
- 已关闭或已完成但用户要求继续时，查询是否有「再次打开/重新打开」等状态；没有时先向用户确认。
- 用 `update_workitem(workitem_id=..., fields={"status": <本次查询到的 identifier>})` 更新，再用 `get_workitem` 确认。

### 4. 过程中：里程碑留痕

- 只在方案确定、遇到阻塞、阶段交付等有意义节点写评论；不要每改一个文件或每跑一个命令就评论。
- 阻塞时先查询当前状态流；如果有挂起/阻塞阶段的状态（例如「挂起」「阻塞」），切过去并写明原因和解除条件；
  没有就保持进行中并写评论。解除后按当前状态流切回进行中。
- 重试或补发评论前，先读当前状态和 `list_workitem_comments`，避免重复流转和重复评论。

### 5. 交付：进入待验证

实现和自测完成后，先重新查询当前状态流，再选择验证阶段的状态；不要直接关闭，也不要在最终答复里只说“已完成”：

- **需求**：选择验证阶段中表示等待验收/测试的状态（例如「待验收」「待验证」）。
- **Bug**：选择验证阶段中表示已修复/等待验证的状态（例如「已修复」）。
- **任务**：如果流程有验证/审核阶段，先进入该状态；没有验证阶段时保持进行中并说明，等待用户确认后再关闭。
- 如果当前状态流没有验证阶段，保持进行中状态并说明，不要为了“交付”而直接关闭。
- 用户明确取消时，选择异常结束阶段的状态（例如「已取消」）；本轮未完成或被阻塞时，保持进行中/阻塞态。
- 创建或提交 PR 后，必须把实际 PR 链接写入对应工作项的云效评论，不能只写在最终答复里。
  先读 `list_workitem_comments`；已有交付评论时用 `update_workitem_comment` 补充或更新，否则用
  `create_workitem_comment` 新增；不要重复发相同链接，PR 未创建时不要伪造链接。

交付评论使用 Markdown，包含真实信息：

```markdown
**进展**
- 变更：<一句话说明>
- 验证：`<命令>` 通过 / <测试结果>
- 交付：commit `<sha>` / PR <链接> / <文件>
- 待办：<剩余工作或“等待验收”>
```

没有 commit/PR 就写“本地修改，未提交”或“PR 尚未创建”；只写实际执行过的验证；不要粘贴密钥、完整日志或无关输出。

### 6. 验收：关闭工作项

- 关闭前再次查询当前状态流，选择正常结束阶段的状态（例如「已完成」「已关闭」「Done」「Closed」）。
- 只有用户明确验收、验证人通过或已有明确验收证据时，才执行关闭。
- Bug 默认停在验证阶段的状态（例如「已修复」「待验证」）；没有验证阶段时保持进行中并说明，除非用户明确要求关闭或项目流程允许自验通过。
- 最终答复报告：工作项编号与标题、状态从 X 到 Y、已验证的内容；如果因权限或状态流限制未更新，明确说明。

### 执行约束

- 用户要求处理某个工作项，即视为授权对该工作项做必要的状态流转和进展评论；不要每次单独询问。不要改负责人、优先级、描述等未授权字段，也不要动其他工作项。
- 每次流转前都重新查询 `list_workitem_statuses(category, workitem_type_id)`，状态名称和 identifier 以当前返回为准；不要硬编码或复用缓存。
- 工具调用失败时如实报告未更新，不要伪造成功，也不要绕过 MCP 手工拼接 OpenAPI 请求。
- 多 Agent 并行时，由负责该工作项的主 Agent 统一更新；子 Agent 只汇报结果，避免并发覆盖。
- 提交 PR 后必须按「交付」章节把 PR 链接同步到工作项评论；只在最终答复里说明不算同步。

## 读取与汇总

- `list_workitems` 每次只接受一个 `category`；汇总项目时分别查询 `Req`、`Bug` 和 `Task`。
- `serialNumber`（例如 `PYNW-5`）适合展示；工具参数需要时使用 `identifier`。
- 判断“最近更新”时使用 `gmtModified`，不要只看创建时间。需要确认内容变化时读取 `get_workitem` 和 `list_workitem_comments`。
- 查询负责人、状态或迭代前，先用 `list_project_members`、`list_workitem_statuses`、`list_sprints` 解析用户给出的名称。
- 用户说“我的待办/我负责的”时，直接使用 `list_workitems(assigned_to_me=true)`；需要确认身份时调用 `get_current_user`，返回的 `identifier` 才是 `assignedTo` 使用的成员 ID。
- `list_workitems` 和 `get_workitem` 的 `isMine` 为 `true`/`false`；`null` 表示未配置 `YUNXIAO_USER_NAME` 且自动识别失败，不要猜，先调用 `get_current_user` 查看原因。
- 多个 Agent 共享同一个 AccessKey 会被视为同一个用户；要区分身份，每个 Agent 使用独立的 AccessKey。

## 描述中的附件

- 图片和附件位于 `document` 的 HTML/JSONML 中。从 URL 的 `fileIdentifier` 提取文件 ID，再调用
  `get_workitem_file(workitem_id=<工作项 identifier>, file_id=<fileIdentifier>)`。
- 不要直接请求 `devops.aliyun.com/projex/api/workitem/file/url?...`；该地址需要认证，会返回 401。
- 宿主不展示 MCP 图片内容时（例如 Codex 优先读取 `structuredContent`），传 `save_to` 保存到本地，
  再用 `view_image` 打开返回的 `path`：
  `get_workitem_file(workitem_id=..., file_id=..., save_to="/tmp/<工作项>-<文件名>")`。
  `save_to` 可以是目录或完整文件名。
- 图片工具结果可直接查看并分析；非图片附件返回 Base64 嵌入资源，最大 10 MiB。需要落盘时同样使用 `save_to`。

## 写入

- 创建工作项前依次查询 `list_workitem_types`、`list_workitem_fields` 和
  `list_workitem_statuses`。`assigned_to`、参与人、验证人使用成员账号 ID。
- `assigned_to` 使用成员 identifier；不要把 `YUNXIAO_USER_NAME` 或显示名直接传给 `assigned_to`。
- 自定义字段（例如 `priority`）通过 `custom_fields` 传选项 identifier，不传显示文本。`description` 使用单独的
  `description` 参数，不要放进 `fields`。
- 状态流转按「工作项状态同步」执行；`fields` 中的 `status` 使用状态 identifier，更新后用 `get_workitem` 验证。
- 创建评论默认使用 Markdown。只有回复已有评论时才传 `parent_id`。
- 只有用户明确要求删除时才调用删除工具并传 `confirm=true`。删除工作项后索引可能延迟刷新。
- 云效没有删除迭代接口；创建迭代前向用户确认名称、负责人和日期，避免不可撤销的误建。

## Bot 边界

当前 Bot 是“开发机器人”，不应尝试修改项目配置或成员。附件上传、工作项关联、工作项动态、
工时/预估、项目创建/删除、迭代修改/删除、代码库和流水线均不在本 MCP 范围内。
