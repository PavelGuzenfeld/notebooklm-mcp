"""MCP server for Google NotebookLM.

Wraps the notebooklm-py SDK to expose NotebookLM functionality
as MCP tools for any MCP-compatible client.

Prerequisites:
    pip install notebooklm-mcp
    notebooklm-auth  # browser-free cookie auth
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

# ---------------------------------------------------------------------------
# Lazy import of the notebooklm client – allows the module to load even when
# the SDK is missing (useful for testing / inspecting tool definitions).
# ---------------------------------------------------------------------------

_nlm_available = True
try:
    from notebooklm import NotebookLMClient
except ImportError:
    _nlm_available = False
    NotebookLMClient = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Lifespan – manages a single shared NotebookLMClient instance
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    client: Any = None  # NotebookLMClient, lazily created
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _exit_stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def get_client(self) -> Any:
        """Lazily create and return the NotebookLM client."""
        if self.client is not None:
            return self.client
        async with self._lock:
            if self.client is not None:
                return self.client
            if not _nlm_available:
                raise RuntimeError(
                    "notebooklm-py is not installed. "
                    "Run: pip install notebooklm-py[browser]"
                )
            storage = os.environ.get("NOTEBOOKLM_AUTH_JSON")
            raw_client = await NotebookLMClient.from_storage(path=storage)
            # NotebookLMClient is an async context manager — enter it
            self.client = await self._exit_stack.enter_async_context(raw_client)
            return self.client

    async def close(self):
        await self._exit_stack.aclose()


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    ctx = AppContext()
    try:
        yield ctx
    finally:
        await ctx.close()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "notebooklm",
    instructions=(
        "MCP server providing access to Google NotebookLM. "
        "Supports notebook/source management, chat, artifact generation, "
        "and web/drive research. Requires prior authentication via "
        "`notebooklm login`."
    ),
    lifespan=app_lifespan,
)


async def _client(ctx: Context) -> Any:
    return await ctx.request_context.lifespan_context.get_client()


def _serialize(obj: Any) -> str:
    """Best-effort JSON serialisation for SDK return types."""
    if obj is None:
        return "OK"
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return json.dumps([_as_dict(o) for o in obj], indent=2, default=str)
    return json.dumps(_as_dict(obj), indent=2, default=str)


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: _as_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_as_dict(i) for i in obj]
    return obj


# ===================================================================
# Notebook tools
# ===================================================================

@mcp.tool()
async def notebook_list(ctx: Context) -> str:
    """List all notebooks in the account."""
    c = await _client(ctx)
    notebooks = await c.notebooks.list()
    return _serialize(notebooks)


@mcp.tool()
async def notebook_create(title: str, ctx: Context) -> str:
    """Create a new notebook with the given title."""
    c = await _client(ctx)
    nb = await c.notebooks.create(title)
    return _serialize(nb)


@mcp.tool()
async def notebook_get(notebook_id: str, ctx: Context) -> str:
    """Get details of a specific notebook by ID."""
    c = await _client(ctx)
    nb = await c.notebooks.get(notebook_id)
    return _serialize(nb)


@mcp.tool()
async def notebook_delete(notebook_id: str, ctx: Context) -> str:
    """Delete a notebook by ID."""
    c = await _client(ctx)
    await c.notebooks.delete(notebook_id)
    return "Deleted"


@mcp.tool()
async def notebook_rename(notebook_id: str, new_title: str, ctx: Context) -> str:
    """Rename a notebook."""
    c = await _client(ctx)
    await c.notebooks.rename(notebook_id, new_title)
    return "Renamed"


@mcp.tool()
async def notebook_summary(notebook_id: str, ctx: Context) -> str:
    """Get the AI-generated summary for a notebook."""
    c = await _client(ctx)
    summary = await c.notebooks.get_summary(notebook_id)
    return _serialize(summary)


# ===================================================================
# Source tools
# ===================================================================

@mcp.tool()
async def source_list(notebook_id: str, ctx: Context) -> str:
    """List all sources in a notebook."""
    c = await _client(ctx)
    sources = await c.sources.list(notebook_id)
    return _serialize(sources)


@mcp.tool()
async def source_add_url(notebook_id: str, url: str, ctx: Context) -> str:
    """Add a URL (webpage or YouTube) as a source to a notebook."""
    c = await _client(ctx)
    src = await c.sources.add_url(notebook_id, url, wait=True)
    return _serialize(src)


@mcp.tool()
async def source_add_text(
    notebook_id: str, title: str, content: str, ctx: Context
) -> str:
    """Add pasted text as a source to a notebook."""
    c = await _client(ctx)
    src = await c.sources.add_text(notebook_id, title, content, wait=True)
    return _serialize(src)


@mcp.tool()
async def source_add_file(
    notebook_id: str, file_path: str, ctx: Context
) -> str:
    """Upload a local file (PDF, text, markdown, docx) as a source."""
    c = await _client(ctx)
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return f"Error: file not found: {p}"
    src = await c.sources.add_file(notebook_id, str(p), wait=True)
    return _serialize(src)


@mcp.tool()
async def source_get(notebook_id: str, source_id: str, ctx: Context) -> str:
    """Get details of a specific source."""
    c = await _client(ctx)
    src = await c.sources.get(notebook_id, source_id)
    return _serialize(src)


@mcp.tool()
async def source_delete(notebook_id: str, source_id: str, ctx: Context) -> str:
    """Delete a source from a notebook."""
    c = await _client(ctx)
    await c.sources.delete(notebook_id, source_id)
    return "Deleted"


@mcp.tool()
async def source_fulltext(notebook_id: str, source_id: str, ctx: Context) -> str:
    """Get the full extracted text of a source."""
    c = await _client(ctx)
    text = await c.sources.get_fulltext(notebook_id, source_id)
    return _serialize(text)


@mcp.tool()
async def source_guide(notebook_id: str, source_id: str, ctx: Context) -> str:
    """Get the AI-generated guide (summary + key topics) for a source."""
    c = await _client(ctx)
    guide = await c.sources.get_guide(notebook_id, source_id)
    return _serialize(guide)


# ===================================================================
# Chat tools
# ===================================================================

@mcp.tool()
async def chat_ask(
    notebook_id: str,
    question: str,
    source_ids: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Ask a question about the notebook's sources.

    Args:
        notebook_id: The notebook to query.
        question: The question to ask.
        source_ids: Optional comma-separated source IDs to scope the query.
    """
    c = await _client(ctx)
    sids = [s.strip() for s in source_ids.split(",") if s.strip()] or None
    result = await c.chat.ask(notebook_id, question, source_ids=sids)
    return _serialize(result)


@mcp.tool()
async def chat_history(notebook_id: str, ctx: Context) -> str:
    """Get the chat history for a notebook."""
    c = await _client(ctx)
    history = await c.chat.get_history(notebook_id)
    return _serialize(history)


@mcp.tool()
async def chat_configure(
    notebook_id: str,
    goal: str = "",
    response_length: str = "",
    custom_prompt: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Configure chat behaviour for a notebook.

    Args:
        notebook_id: Target notebook.
        goal: Optional system-level goal.
        response_length: Optional length hint.
        custom_prompt: Optional custom system prompt.
    """
    c = await _client(ctx)
    kwargs: dict[str, str] = {}
    if goal:
        kwargs["goal"] = goal
    if response_length:
        kwargs["response_length"] = response_length
    if custom_prompt:
        kwargs["custom_prompt"] = custom_prompt
    await c.chat.configure(notebook_id, **kwargs)
    return "Configured"


# ===================================================================
# Artifact tools (audio, reports, quizzes, etc.)
# ===================================================================

@mcp.tool()
async def artifact_list(notebook_id: str, ctx: Context) -> str:
    """List all generated artifacts in a notebook."""
    c = await _client(ctx)
    arts = await c.artifacts.list(notebook_id)
    return _serialize(arts)


@mcp.tool()
async def artifact_generate_audio(
    notebook_id: str,
    source_ids: str = "",
    instructions: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Generate an audio overview (podcast) from notebook sources.

    Args:
        notebook_id: Target notebook.
        source_ids: Optional comma-separated source IDs to include.
        instructions: Optional instructions for audio generation.
    """
    c = await _client(ctx)
    kwargs: dict[str, Any] = {"notebook_id": notebook_id}
    if source_ids:
        kwargs["source_ids"] = [s.strip() for s in source_ids.split(",") if s.strip()]
    if instructions:
        kwargs["instructions"] = instructions
    art = await c.artifacts.generate_audio(**kwargs)
    return _serialize(art)


@mcp.tool()
async def artifact_generate_report(
    notebook_id: str,
    topic: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Generate a written report from notebook sources."""
    c = await _client(ctx)
    kwargs: dict[str, Any] = {"notebook_id": notebook_id}
    if topic:
        kwargs["topic"] = topic
    art = await c.artifacts.generate_report(**kwargs)
    return _serialize(art)


@mcp.tool()
async def artifact_generate_study_guide(notebook_id: str, ctx: Context) -> str:
    """Generate a study guide from notebook sources."""
    c = await _client(ctx)
    art = await c.artifacts.generate_study_guide(notebook_id)
    return _serialize(art)


@mcp.tool()
async def artifact_generate_quiz(notebook_id: str, ctx: Context) -> str:
    """Generate a quiz from notebook sources."""
    c = await _client(ctx)
    art = await c.artifacts.generate_quiz(notebook_id)
    return _serialize(art)


@mcp.tool()
async def artifact_generate_flashcards(notebook_id: str, ctx: Context) -> str:
    """Generate flashcards from notebook sources."""
    c = await _client(ctx)
    art = await c.artifacts.generate_flashcards(notebook_id)
    return _serialize(art)


@mcp.tool()
async def artifact_generate_mind_map(notebook_id: str, ctx: Context) -> str:
    """Generate a mind map from notebook sources."""
    c = await _client(ctx)
    art = await c.artifacts.generate_mind_map(notebook_id)
    return _serialize(art)


@mcp.tool()
async def artifact_download_audio(
    notebook_id: str, artifact_id: str, output_path: str, ctx: Context
) -> str:
    """Download a generated audio artifact to a local file."""
    c = await _client(ctx)
    p = Path(output_path).expanduser().resolve()
    await c.artifacts.download_audio(notebook_id, artifact_id, str(p))
    return f"Downloaded to {p}"


@mcp.tool()
async def artifact_poll_status(
    notebook_id: str, artifact_id: str, ctx: Context
) -> str:
    """Check the generation status of an artifact."""
    c = await _client(ctx)
    status = await c.artifacts.poll_status(notebook_id, artifact_id)
    return _serialize(status)


@mcp.tool()
async def artifact_delete(notebook_id: str, artifact_id: str, ctx: Context) -> str:
    """Delete an artifact."""
    c = await _client(ctx)
    await c.artifacts.delete(notebook_id, artifact_id)
    return "Deleted"


# ===================================================================
# Research tools
# ===================================================================

@mcp.tool()
async def research_start(
    notebook_id: str,
    query: str,
    source: str = "web",
    mode: str = "fast",
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """Start a research task (web or Google Drive search).

    Args:
        notebook_id: Target notebook.
        query: Research query.
        source: "web" or "drive".
        mode: "fast" or "deep".
    """
    c = await _client(ctx)
    result = await c.research.start(notebook_id, query, source=source, mode=mode)
    return _serialize(result)


@mcp.tool()
async def research_poll(notebook_id: str, ctx: Context) -> str:
    """Poll the status of an ongoing research task."""
    c = await _client(ctx)
    status = await c.research.poll(notebook_id)
    return _serialize(status)


# ===================================================================
# Sharing tools
# ===================================================================

@mcp.tool()
async def sharing_status(notebook_id: str, ctx: Context) -> str:
    """Get the sharing status of a notebook."""
    c = await _client(ctx)
    status = await c.sharing.get_status(notebook_id)
    return _serialize(status)


@mcp.tool()
async def sharing_set_public(
    notebook_id: str, public: bool, ctx: Context
) -> str:
    """Make a notebook public or private."""
    c = await _client(ctx)
    await c.sharing.set_public(notebook_id, public)
    return f"Public: {public}"


# ===================================================================
# Entry point
# ===================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="NotebookLM MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host for HTTP/SSE transports (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=8484,
        help="Port for HTTP/SSE transports (default: 8484)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
