# 发布说明

发布流程分两步：先发 PyPI，再发官方 MCP Registry。Registry 会校验 PyPI 包 README 中的 `mcp-name` 标记，所以顺序不能颠倒。

## 1. 更新版本

同时修改两处版本号，`tests/test_packaging.py` 会校验它们一致：

- `pyproject.toml` 的 `[project].version`
- `server.json` 的 `version` 和 `packages[0].version`

## 2. 发布到 PyPI

```bash
uv build
UV_PUBLISH_TOKEN=pypi-... uv publish
```

发布后确认包元数据里带有 Registry 归属标记：

```bash
curl -s https://pypi.org/pypi/yunxiao-projex-mcp/json \
  | python3 -c "import sys,json; print('io.github.MrLinWang/aliyun-yunxiao-projex-mcp' in json.load(sys.stdin)['info']['description'])"
```

应输出 `True`。

## 3. 发布到 MCP Registry

```bash
mcp-publisher login github
mcp-publisher validate server.json
mcp-publisher publish server.json
```

`mcp-publisher` 从 [modelcontextprotocol/registry](https://github.com/modelcontextprotocol/registry/releases) 下载。GitHub 命名空间授予的是 `io.github.<username>/*`，所以 `server.json` 中的名称段可以与仓库名不同。

## 4. 验证

```bash
curl -s 'https://registry.modelcontextprotocol.io/v0/servers?search=yunxiao-projex-mcp&version=latest'
curl -s 'https://registry.modelcontextprotocol.io/v0/servers?search=aliyun&version=latest'
```

两条都应返回该服务。Magpie 的 Discover 搜索的是 Registry 中的服务名，因此名称里保留 `aliyun`、`yunxiao`、`projex`、`mcp` 这些关键词才能被搜到。

要出现在 Magpie Discover 的默认页（空搜索），需要向 [yetone/magpie](https://github.com/yetone/magpie) 的 `internal/library/market.go` 提交 featured 条目 PR；Registry 发布只保证能被关键词搜索到。
