# iOS MCP Server

A Model Context Protocol (MCP) server that allows Large Language Models (LLMs) to access, scan, and search files on a connected iOS device.

## Features

-   **Device Access**: Connects to iPhone via USB using `libimobiledevice`.
-   **Semantic Search**: Uses **ChromaDB** (Vector Database) to enable natural language search (e.g., "Find photos of my trip to Paris").
-   **Exact Filtering**: Supports precise metadata filtering (e.g., `{"Model": "iPhone 12"}`).
-   **Incremental Scanning**: "Execute once, query many" architecture. Scans are cached, so subsequent queries are instant.
-   **Introspection**: Tools to discover available metadata fields and fix typos.

## Prerequisites

1.  **macOS**: This tool relies on macOS-specific tools for iOS connectivity.
2.  **System Tools**:
    ```bash
    brew install libimobiledevice ifuse exiftool
    ```
3.  **Python 3.10+**

## Installation

1.  Clone the repository:
    ```bash
    git clone <your-repo-url>
    cd ios_mcp
    ```

2.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### 1. Connect your iPhone
Connect your iPhone via USB and ensure you have "Trusted" the computer on the device.

### 2. Start the MCP Server
You can run the server directly:

```bash
mcp run src/server.py
```

### 3. Client Configuration

#### Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ios-mcp": {
      "command": "mcp",
      "args": ["run", "/absolute/path/to/ios_mcp/src/server.py"]
    }
  }
}
```

#### VS Code (MCP Extension)
Add to your `settings.json` (or `.vscode/settings.json`):
```json
{
  "mcp.servers": {
    "ios-mcp": {
      "command": "mcp",
      "args": ["run", "/absolute/path/to/ios_mcp/src/server.py"]
    }
  }
}
```

#### Perplexity
If using the Perplexity Desktop app or MCP integration:
1.  Go to **Settings** > **MCP Servers**.
2.  Add a new server:
    *   **Name**: `ios-mcp`
    *   **Command**: `mcp`
    *   **Args**: `run /absolute/path/to/ios_mcp/src/server.py`

#### Antigravity / AI Agents
To use this tool with Antigravity or other AI coding agents, ensure the server is registered in the agent's MCP configuration (often `mcp.json` or via the environment).

**Generic Config**:
```json
{
  "ios-mcp": {
    "command": "mcp",
    "args": ["run", "${workspaceFolder}/src/server.py"]
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_connected_devices` | Lists UDIDs of connected iOS devices. |
| `scan_and_cache_photos` | Mounts the device, scans DCIM, and indexes metadata into the Vector DB. |
| `search_files` | Semantic search using natural language (e.g., "Photos of sunset"). |
| `filter_files` | Exact metadata filtering (e.g., `{"Flash": true}`). |
| `get_metadata_keys` | Lists all available metadata fields (columns). |
| `find_similar_metadata_keys` | Finds valid keys similar to a typo (e.g., "Date" -> "DateTimeOriginal"). |
| `get_file_content` | Reads the content of a specific file. |

## Testing

### Local Test (No MCP)
Run the local test script to verify device connectivity and database operations without the MCP layer:

```bash
python3 tests/test_local.py
```

### LLM Test
Once connected to an LLM:
1.  **Scan**: "Scan my iPhone for photos."
2.  **Search**: "Find photos taken in 2024."
3.  **Introspect**: "What metadata fields are available?"