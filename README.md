# OpenBB Documentation MCP Server

A Model Context Protocol (MCP) server that provides OpenBB Workspace documentation to AI assistants through a two-step retrieval workflow.

## What it does

This server exposes two tools that work together to retrieve relevant OpenBB documentation:

### 1. `identify_openbb_docs_sections`
- Takes a user query
- Fetches the complete OpenBB documentation table of contents
- Provides it to the LLM with instructions to identify up to 3 relevant section titles
- Returns the raw TOC for intelligent analysis

### 2. `fetch_openbb_content`
- Takes the section titles identified in step 1 + the original user query
- Fetches the full OpenBB documentation
- Extracts only the relevant sections
- Returns the content with OpenBB Copilot-compatible citation format instructions

## Workflow

1. LLM calls `identify_openbb_docs_sections` with user's question
2. LLM analyzes the TOC and identifies relevant sections (up to 3)
3. LLM calls `fetch_openbb_content` with those section titles
4. LLM uses the extracted content to answer the user's question with proper citations

## How to run

Start the server locally:

```bash
python server.py
```

The server will start on port 8000 by default. You can change it with:

```bash
PORT=8014 python server.py
```

The MCP endpoint will be available at `http://localhost:8000/mcp`

## Configuration

The server is pre-configured with CORS for:
- `https://pro.openbb.co`
- `https://pro.openbb.dev`
- `http://localhost:1420`

## Dependencies

Install requirements:

```bash
pip install -r requirements.txt
```

Requires Python 3.10+
