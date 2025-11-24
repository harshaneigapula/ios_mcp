# LLM Testing Instructions

## Prerequisites
1. Ensure `mcp` and `tinydb` are installed: `pip install -r requirements.txt`
2. Ensure `libimobiledevice` and `ifuse` are installed on your Mac (`brew install libimobiledevice ifuse`).
3. Connect your iPhone via USB.

## Running the Server
Run the MCP server using the `mcp` CLI or directly with python if you have a runner.
Since we used `FastMCP`, you can run it like this:

```bash
mcp run src/server.py
```

Or if you are using Claude Desktop or another client, configure it to run this script.

## Testing with LLM
Once connected, ask the LLM the following:

1.  **"List my connected iOS devices."**
    *   *Expected*: Should show your iPhone's UDID.
2.  **"Scan my iPhone for photos."**
    *   *Expected*: Should mount the phone, scan DCIM, and say how many files were indexed.
3.  **"Find photos taken with an iPhone 12"** (or whatever model you have).
    *   *Expected*: Should query the local database and return results.
4.  **"Show me the details of the first photo found."**
    *   *Expected*: Should return metadata.

## Troubleshooting
- If mounting fails, ensure you have trusted the computer on your iPhone.
- If `idevice_id` is not found, make sure `libimobiledevice` is in your PATH.
