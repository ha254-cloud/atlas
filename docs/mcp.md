# Atlas MCP Server

The Atlas MCP Server exposes Atlas capabilities as **tools** that any MCP-compatible AI client (Claude, ChatGPT, Cursor, VS Code) can call.

## Authentication

MCP requests authenticate via an API key in the `X-Atlas-API-Key` header.

Create a key at `POST /api/v1/mcp/keys` (requires JWT auth). The raw key is shown once.

## Available Tools

| Tool | Description |
|------|-------------|
| `analyze_claim` | Run AI analysis on a claim |
| `estimate_recovery` | Estimate recovery opportunity value |
| `generate_appeal` | Draft an appeal letter |
| `classify_denial` | Classify the denial reason |
| `check_status` | Check claim status + denials + recovery cases |
| `sync_claims` | Sync claims from an EHR connector |
| `reconcile_payment` | Apply a payment to a claim |

## Request Format

```
POST /api/v1/mcp/tools/analyze_claim
X-Atlas-API-Key: atlas_<your-key>
Content-Type: application/json

{
  "claim_id": 123
}
```

## Response Format

Every tool returns the same envelope:

```json
{
  "success": true,
  "tool": "analyze_claim",
  "data": { ... },
  "error": null
}
```

## Adding a New Tool

1. Create `app/mcp/tools/my_tool.py` inheriting `BaseTool`
2. Implement `async execute(db, organization_id, **params) -> MCPResponse`
3. Register in `app/mcp/server.py`: `registry.register(MyTool())`
4. Add a typed request schema in `app/mcp/schemas/requests.py`
5. Add an endpoint in `app/mcp/server.py`
