# plurity-mcp

Unified [MCP](https://modelcontextprotocol.io) server for all Plurity services — **Audit**, **Toll**, and **Intelligence** — using a single API key.

## Installation

```bash
uvx plurity-mcp
```

Or install permanently:

```bash
uv tool install plurity-mcp
```

## Quick start

**1. Get an API key**

Log in to [account.plurity.ai](https://account.plurity.ai) → Settings → API Keys → Create key.
Grant the scopes for each service you want to use (`audit`, `toll`, `intelligence`).

**2. Run the setup wizard**

```bash
plurity-mcp-setup
```

The wizard validates your key and saves it to `~/.config/plurity/config.toml`.

**3. Add to your MCP client**

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "plurity": {
      "command": "uvx",
      "args": ["plurity-mcp"],
      "env": {
        "PLURITY_API_KEY": "plt_your_key_here"
      }
    }
  }
}
```

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PLURITY_API_KEY` | — | Your `plt_*` API key (**required**) |
| `PLURITY_ACCOUNTS_URL` | `https://account.plurity.ai` | Override accounts API URL |
| `PLURITY_AUDIT_URL` | `https://audit.plurity.ai` | Override Audit API URL |
| `PLURITY_TOLL_URL` | `https://toll.plurity.ai` | Override Toll API URL |
| `PLURITY_INTELLIGENCE_URL` | `https://intelligence.plurity.ai` | Override Intelligence API URL |
| `PLURITY_AUDIT_ENABLED` | `true` | Set to `false` to disable Audit tools |
| `PLURITY_TOLL_ENABLED` | `true` | Set to `false` to disable Toll tools |
| `PLURITY_INTELLIGENCE_ENABLED` | `true` | Set to `false` to disable Intelligence tools |

### Config file (`~/.config/plurity/config.toml`)

```toml
[mcp]
api_key = "plt_..."
accounts_url = "https://account.plurity.ai"
audit_base_url = "https://audit.plurity.ai"
toll_base_url = "https://toll.plurity.ai"
intelligence_base_url = "https://intelligence.plurity.ai"
audit_enabled = true
toll_enabled = true
intelligence_enabled = true
```

Environment variables take precedence over the config file.

### Service activation

On startup the server:

1. Validates your API key against plurity-accounts
2. Reads the key's scopes (e.g. `["audit", "toll"]`)
3. Registers only the tools for services the key is scoped for
4. Applies your `*_ENABLED` overrides — you can disable services the key has access to, but you cannot enable services the key lacks a scope for

If the key is invalid the server exits immediately with a clear error message visible in your MCP client.

## Tools

### Audit (GEO readiness)

| Tool | Description |
|---|---|
| `submit_audit_scan` | Queue a URL for AI-readiness analysis |
| `get_audit_scan` | Get scan status and results by ID |
| `get_audit_scan_by_url` | Look up the latest scan for a URL |
| `run_audit` | Submit and wait until complete (blocking) |

### Toll (agent traffic + llms.txt)

| Tool | Description |
|---|---|
| `list_toll_sites` | List your sites/pages |
| `create_toll_site` | Create a new site |
| `get_toll_site` | Get site details including site key |
| `update_toll_site` | Update name, domain, cache TTL, llms.txt mode |
| `get_toll_installation_instructions` | Get integration code snippets for HTML/Next.js/React/GTM |
| `list_toll_qa_pairs` | List Q&A pairs in a site's llms.txt |
| `create_toll_qa_pair` | Add a Q&A entry to llms.txt |
| `update_toll_qa_pair` | Edit a Q&A entry (or publish/unpublish it) |
| `delete_toll_qa_pair` | Remove a Q&A entry |
| `get_toll_traffic` | Agent traffic chart data (today/week/month/year) |

### Intelligence (question & topic monitoring)

| Tool | Description |
|---|---|
| `list_intelligence_sources` | Browse the global source catalogue |
| `list_subscribed_intelligence_sources` | List sources your org follows |
| `subscribe_intelligence_source` | Subscribe to a source |
| `unsubscribe_intelligence_source` | Unsubscribe from a source |
| `request_intelligence_source` | Add a new source by URL (auto-subscribes) |
| `list_intelligence_source_content` | List raw scraped documents |
| `list_intelligence_qa_pairs` | Browse the Q&A feed with filters |
| `approve_intelligence_qa_pair` | Move a Q&A pair into your knowledge base |
| `skip_intelligence_qa_pair` | Dismiss a Q&A pair from the feed |

## Development

```bash
git clone https://github.com/plurity-oss/plurity-mcp
cd plurity-mcp
uv sync
uv run plurity-mcp-setup    # set up key
uv run plurity-mcp          # run locally
```

## License

MIT
