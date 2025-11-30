# LLM Testing Instructions

This guide helps you verify the iOS MCP Server's functionality using an LLM (Claude, etc.).

## Prerequisites

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **System Tools**:
    Ensure `libimobiledevice`, `ifuse`, and `exiftool` are installed:
    ```bash
    brew install libimobiledevice ifuse exiftool
    ```
3.  **Connect Device**: Connect your iPhone via USB and ensure it is "Trusted".

## Running the Server

Run the MCP server using the `mcp` CLI:

```bash
mcp run src/server.py
```

Or configure your client (Claude Desktop, etc.) to run this command.

---

## Test Scenarios

Once connected to the LLM, try the following prompts to verify different capabilities.

### 1. Basic Connection & Scanning

*   **"List my connected iOS devices."**
    *   *Expected*: Should show your iPhone's UDID.
*   **"Scan my iPhone for photos."**
    *   *Expected*: Should mount the phone, scan the DCIM directory, and report the number of files indexed.

### 2. Natural Language Search (Semantic)
ʼSearch is based on the EXIF Metadata of the photos. iPhone generates some of the stats like face information, location, etc. Search might not work great if the metadata is not available.ʼ  

*   **"Find photos of mountains."**
*   **"Show me videos from my trip to Paris in 2024."**
    *   *Expected*: The LLM should use `search_files` or `run_advanced_query` with a semantic query and return relevant results.

### 3. Exact Filtering & Metadata

*   **"Find all photos taken with an iPhone 12."**
*   **"Count how many photos have ISO greater than 100."**
    *   *Expected*: The LLM should use `filter_files` or `count_files` with structured JSON criteria (e.g., `{"Model": "iPhone 12"}`).

### 4. Advanced Analysis (Aggregation & Grouping)

*   **"Group my photos by Camera Model and show me the count for each."**
    *   *Expected*: Should use `group_files(field="Model")`.
*   **"Calculate the average ISO for each camera model."**
    *   *Expected*: Should use `run_aggregation_pipeline` with `$group` and `$avg`.
    ```json
    [
      {"$group": {
        "_id": "$Model",
        "avg_iso": {"$avg": "$ISO"}
      }}
    ]
    ```

### 5. Introspection

*   **"What metadata fields are available for me to search?"**
    *   *Expected*: Should call `get_metadata_keys`.

### 6. Image Retrieval

*   **"Read the first image found in the previous search."**
    *   *Expected*: Should call `read_image` with the file path and return a base64 string (or describe the image if the LLM supports vision).

---

## Troubleshooting

-   **Mounting Fails**: Ensure the device is unlocked and "Trusted". Try running `idevicepair pair` in the terminal.
-   **No Results**: Ensure `scan_and_cache_photos` was run at least once.
-   **"Command not found"**: Ensure you are running the server in the correct python environment.
