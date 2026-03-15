# NotebookLM MCP Server

MCP server that exposes Google NotebookLM as tools for any MCP-compatible client.

Built on [notebooklm-py](https://github.com/teng-lin/notebooklm-py) (unofficial SDK).

## Quick Start (Step by Step)

### Step 1: Install

```bash
# Clone or navigate to the project
cd notebooklm-mcp

# Option A: using uv (recommended)
uv venv .venv && source .venv/bin/activate && uv pip install -e .

# Option B: using pip
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

### Step 2: Authenticate with Google NotebookLM

```bash
notebooklm-auth
```

This will show:
```
╔══════════════════════════════════════════════════════════════╗
║           NotebookLM CLI Authentication                     ║
╚══════════════════════════════════════════════════════════════╝

Open this URL in your browser and log in:

  https://notebooklm.google.com/
```

Then follow these steps:

1. Open **https://notebooklm.google.com/** in your browser
2. Log in with your Google account
3. Open **DevTools** (press `F12`)
4. Go to the **Network** tab
5. Refresh the page (`F5`)
6. Right-click the first request (`notebooklm.google.com`)
7. Click **Copy** > **Copy as cURL**
8. Paste into the terminal and press Enter twice

### Step 3: Verify authentication

```bash
notebooklm-auth --verify
```

Expected output:
```
Auth file: ~/.notebooklm/storage_state.json
Cookies: <N> found
Verifying against https://notebooklm.google.com/ ...
CSRF token: <token>...
Session ID: <session_id>...

Authentication is VALID.
```

### Step 4: Connect to your MCP client

See [Client Configuration](#client-configuration) below for your specific tool.

### Step 5: Start using NotebookLM tools

Once connected, you can use any of the 31 tools — list notebooks, add sources, ask questions, generate podcasts, and more.

## Running

### stdio (default — for local MCP clients)

```bash
notebooklm-mcp
```

### HTTP (for remote clients, web UIs, multi-client setups)

```bash
notebooklm-mcp --transport streamable-http --port 8484
```

### SSE (Server-Sent Events)

```bash
notebooklm-mcp --transport sse --port 8484
```

## Client Configuration

### Claude Code
```bash
claude mcp add notebooklm -- notebooklm-mcp
```

### Cursor
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "notebooklm-mcp"
    }
  }
}
```

### Windsurf / Continue / Cline
Add to your MCP config:
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "notebooklm-mcp"
    }
  }
}
```

### HTTP clients (any language/tool)
```bash
# Start the server
notebooklm-mcp --transport streamable-http --port 8484

# Connect from any MCP client at:
#   http://localhost:8484/mcp
```

## Available Tools (31)

### Notebooks
| Tool | Description |
|------|-------------|
| `notebook_list` | List all notebooks |
| `notebook_create` | Create a new notebook |
| `notebook_get` | Get notebook details |
| `notebook_delete` | Delete a notebook |
| `notebook_rename` | Rename a notebook |
| `notebook_summary` | Get AI-generated summary |

### Sources
| Tool | Description |
|------|-------------|
| `source_list` | List sources in a notebook |
| `source_add_url` | Add a URL or YouTube link |
| `source_add_text` | Add pasted text |
| `source_add_file` | Upload a local file (PDF, markdown, docx) |
| `source_get` | Get source details |
| `source_delete` | Delete a source |
| `source_fulltext` | Get extracted text |
| `source_guide` | Get AI summary of a source |

### Chat
| Tool | Description |
|------|-------------|
| `chat_ask` | Ask questions about notebook sources |
| `chat_history` | Get conversation history |
| `chat_configure` | Set chat goal, length, or custom prompt |

### Artifacts
| Tool | Description |
|------|-------------|
| `artifact_list` | List generated artifacts |
| `artifact_generate_audio` | Generate podcast/audio overview |
| `artifact_generate_report` | Generate a report |
| `artifact_generate_study_guide` | Generate study guide |
| `artifact_generate_quiz` | Generate quiz |
| `artifact_generate_flashcards` | Generate flashcards |
| `artifact_generate_mind_map` | Generate mind map |
| `artifact_download_audio` | Download audio file |
| `artifact_poll_status` | Check generation status |
| `artifact_delete` | Delete an artifact |

### Research
| Tool | Description |
|------|-------------|
| `research_start` | Start web or Drive research |
| `research_poll` | Check research status |

### Sharing
| Tool | Description |
|------|-------------|
| `sharing_status` | Get sharing status |
| `sharing_set_public` | Toggle public/private |

## Authentication

Two options — no Playwright required for either:

### Option 1: Interactive CLI (recommended)
```bash
notebooklm-auth
```
Opens instructions to copy cookies from your browser's DevTools. Supports:
- Copy as cURL (right-click in Network tab)
- Raw Cookie header
- JSON export from browser extensions

### Option 2: Environment variable
```bash
export NOTEBOOKLM_AUTH_JSON='{"cookies":[{"name":"SID","value":"...","domain":".google.com","path":"/","expires":-1,"httpOnly":true,"secure":true,"sameSite":"None"}]}'
notebooklm-mcp
```

### Verify auth
```bash
notebooklm-auth --verify
```

Cookies are stored in `~/.notebooklm/storage_state.json` and expire periodically.

## Caveats

- Uses undocumented Google APIs — may break without notice
- Not affiliated with Google
- Heavy usage may trigger rate limits
- For personal/research use, not production
