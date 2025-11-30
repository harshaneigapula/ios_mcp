---
title: iOS MCP Server
emoji: 📱
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.0.1
app_file: app.py
pinned: false
tags:
- building-mcp-track-consumer
- mcp
- ios
- agent
license: mit
short_description: MCP Server to connect to IOS Devices locally
---

# iOS MCP Server

A Model Context Protocol (MCP) server that allows Large Language Models (LLMs) to access, scan, and search photos on a connected iOS device.

### 📺 [Watch the Demo Video](https://drive.google.com/file/d/1yyqCKYXskhf4JLdMTkgvbPJ6gCqacOG3/view?usp=sharing)

## Features

-   **Device Access**: Connects to iPhone via USB using `libimobiledevice`.
-   **Smart File Copying**: Organize and copy files to your computer with auto-renaming based on metadata.
-   **Semantic Search**: Uses **ChromaDB** (Vector Database) to enable natural language search (e.g., "Find photos of my trip to Paris").
-   **Exact Filtering**: Supports precise metadata filtering (e.g., `{"Model": "iPhone 12"}`).
-   **Incremental Scanning**: "Execute once, query many" architecture. Scans are cached, so subsequent queries are instant.
-   **Introspection**: Tools to discover available metadata fields and fix typos.

## 🏆 MCP Hackathon Submission

**Track:** `building-mcp-track-consumer`


### 👥 Team Members
- [harshaneigapula](https://huggingface.co/harshaneigapula)

### 📢 Social Media Post
- [LinkedIn Submission Post](https://www.linkedin.com/posts/harsha-neigapula_genai-appleintelligence-mcp-activity-7400967108257566720-qkys?utm_source=share&utm_medium=member_desktop&rcm=ACoAAA0zp78BxBTd9sGA6ASEC72oTtD5eqi-_6E)

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
    git clone https://github.com/harshaneigapula/ios_mcp
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
      "command": "python",
      "args": ["/absolute/path/to/ios_mcp/src/server.py"]
    }
  }
}
```


#### Perplexity
If using the Perplexity Desktop app or MCP integration:
1.  Go to **Settings** > **MCP Servers**.
2.  Add a new server:
    *   **Name**: `ios-mcp`
    *   **Command**: `python`
    *   **Args**: `/absolute/path/to/ios_mcp/src/server.py`


## Available Tools

| Tool | Description |
|------|-------------|
| `list_connected_devices` | Lists UDIDs of connected iOS devices. |
| `scan_and_cache_photos` | Mounts the device, scans DCIM, and indexes metadata into the Vector DB. |
| `search_files` | Semantic search using natural language for photos based on Photo Metadata (e.g., "Photos of Apple 12 taken during 2024"). |
| `filter_files` | Exact metadata filtering (e.g., `{"Flash": true}`). |
| `count_files` | Count files matching semantic or exact criteria. |
| `group_files` | Group files by a field and return counts (e.g., group by "Model"). |
| `run_advanced_query` | Complex query with sorting, pagination, and projection. |
| `run_aggregation_pipeline` | Multi-stage data processing pipeline (MongoDB style). |
| `get_metadata_keys` | Lists all available metadata fields (columns). |
| `find_similar_metadata_keys` | Finds valid keys similar to a typo. |
| `read_image` | Reads and resizes an image, returning base64 data. |
| `copy_files_to_local` | Copies files to a local directory, with optional renaming. |
| `mount_device_for_file_access` | Manually mount the device. |
| `check_db_status` | Check database connection health. |

## 🧠 Advanced Data Analysis

The server supports powerful data analysis capabilities modeled after MongoDB.

### Aggregation Pipeline (`run_aggregation_pipeline`)
Process data through a multi-stage pipeline. Supported stages: `$match`, `$group`, `$project`, `$sort`, `$limit`, `$count`.

**Example: Find camera models with average ISO > 200**
```json
[
  {"$match": {"Make": "Apple"}},
  {"$group": {
    "_id": "$Model", 
    "avg_iso": {"$avg": "$ISO"},
    "count": {"$sum": 1}
  }},
  {"$match": {"avg_iso": {"$gt": 200}}},
  {"$sort": {"count": -1}}
]
```

### Advanced Querying (`run_advanced_query`)
Perform complex queries with sorting and pagination.

**Example: Get the 10 most recent photos**
```json
{
  "where": {"MIMEType": "image/jpeg"},
  "sort_by": "CreationDate",
  "sort_order": "desc",
  "limit": 10
}
```

### Grouping (`group_files`)
Quickly see the distribution of your files.
- **Input**: `field="Model"`
- **Output**: `{"iPhone 12": 150, "iPhone 13 Pro": 42}`

## 📂 File Management

### Copying & Organizing Files (`copy_files_to_local`)
The `copy_files_to_local` tool allows you to copy files from the iOS device to your local machine. 

**Key Feature: Renaming for Organization**
You can provide a list of `new_filenames` matching the source files. This is powerful when combined with metadata. For example, you can rename files based on their creation date or location to organize them automatically.

**Example: Copy and Rename**
```python
# Conceptual example of what the LLM does
source_files = ["/tmp/iphone/DCIM/IMG_001.JPG", "/tmp/iphone/DCIM/IMG_002.JPG"]
new_names = ["2024-01-01_Paris_001.jpg", "2024-01-01_Paris_002.jpg"]

copy_files_to_local(source_paths=source_files, destination_folder="/Users/me/Photos", new_filenames=new_names)
```

## 🛠️ Utility Tools

- **`read_image`**: Reads an image file (JPG, HEIC, etc.) from the device, resizes it (max 1024px), and returns a base64 encoded string. Useful for passing images to Vision-capable LLMs. (Most of the LLMs don't support image input as of now. More testing is needed here.)
- **`mount_device_for_file_access`**: Manually mounts the device if you need to perform operations outside the standard scan flow.

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