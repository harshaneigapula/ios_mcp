from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any
import os
try:
    from .database import Database
    from .device import mount_device, scan_photos, get_devices, get_device_info, unmount_device
except ImportError:
    from database import Database
    from device import mount_device, scan_photos, get_devices, get_device_info, unmount_device

# Initialize FastMCP server
mcp = FastMCP("iOS MCP Server")

# Initialize Database
db = Database()

# Configuration
MOUNT_POINT = "/tmp/iphone"

@mcp.tool()
def list_connected_devices() -> str:
    """
    List all connected iOS devices.
    """
    rc, out, err = get_devices()
    if rc != 0:
        return f"Error listing devices: {err}"
    return out

@mcp.tool()
def get_device_details(udid: str) -> str:
    """
    Get detailed info about a specific device by UDID.
    """
    rc, info, err = get_device_info(udid)
    if rc != 0:
        return f"Error getting info: {err}"
    return str(info)

@mcp.tool()
def scan_and_cache_photos() -> str:
    """
    Mounts the device, scans for photos/videos in DCIM, and caches metadata in the local database.
    Returns the number of files indexed.
    """
    # 1. Mount
    success, msg = mount_device(MOUNT_POINT)
    if not success:
        return f"Failed to mount: {msg}"
    
    # 2. Scan
    try:
        # Optimization: Fetch existing files map to skip re-scanning
        existing_files = db.get_existing_files_map()
        metadata_list = scan_photos(MOUNT_POINT, existing_files=existing_files)
    except Exception as e:
        return f"Error scanning photos: {e}"
        
    # 3. Cache
    if metadata_list:
        db.upsert_files(metadata_list)
        return f"Successfully indexed {len(metadata_list)} new files. (Skipped {len(existing_files)})"
    else:
        return f"No new files found. (Already cached {len(existing_files)})"

@mcp.tool()
def search_files(query: str, n_results: int = 10) -> str:
    """
    Search for files using natural language.
    Example: "Find photos of mountains" or "Videos from 2024"
    n_results is the number of results to return. If not needed pass None.  
    """
    # ChromaDB handles the embedding and semantic search
    results = db.query_files(query=query, n_results=n_results)
    return str(results)

@mcp.tool()
def filter_files(criteria: str, n_results: int = 10) -> str:
    """
    Filter files by exact metadata values using MongoDB-style operators.
    Input must be a valid JSON string.
    n_results is the number of results to return. If not needed pass None.  

    Supported Operators:
    - Comparison: $eq (equal), $ne (not equal), $gt (greater than), $gte (greater than or equal), $lt (less than), $lte (less than or equal)
    - Inclusion: $in (in list), $nin (not in list)
    - Logical: $and, $or

    CRITICAL SYNTAX RULES:
    1. For multiple conditions, you MUST use "$and" or "$or". Implicit AND (e.g., {"Field1": "A", "Field2": "B"}) is NOT supported and will fail.
    2. Field names are case-sensitive (e.g., "EXIF:ISO", "Model").
    
    Examples:
    - Simple equality: {"Model": "iPhone 12"}
    - Comparison: {"EXIF:ISO": {"$gte": 100}}
    - Multiple conditions (REQUIRED syntax):
      {
        "$and": [
            {"EXIF:ISO": {"$gte": 100}},
            {"Model": "iPhone 12"}
        ]
      }
    - OR condition:
      {
        "$or": [
            {"Model": "iPhone 12"},
            {"Model": "iPhone 13"}
        ]
      }
    """
    import json
    try:
        where_clause = json.loads(criteria)
    except json.JSONDecodeError:
        return "Error: Criteria must be a valid JSON string."
        
    results = db.query_files(where=where_clause)
    return str(results)

@mcp.tool()
def mount_device_for_file_access():
    """
    Mount the device for file access. 
    Uses the configured mount point.
    """
    success, msg = mount_device(MOUNT_POINT)
    if not success:
        return f"Failed to mount: {msg}"
    return "Mounted successfully"

@mcp.tool()
def unmount_device_for_file_access():
    """
    Unmount the device for file access.
    """
    success, msg = unmount_device(MOUNT_POINT)
    if not success:
        return f"Failed to unmount: {msg}"
    return "Unmounted successfully"

@mcp.tool()
def get_metadata_keys() -> str:
    """
    Get a list of all available metadata keys (columns) in the database.
    Use this to understand what fields you can filter by.
    """
    keys = list(db.get_all_keys())
    keys.sort()
    return str(keys)

@mcp.tool()
def find_similar_metadata_keys(key_name: str) -> str:
    """
    Find valid metadata keys that are similar to the provided key_name.
    Use this if a filter fails or if you are unsure of the exact field name.
    """
    matches = db.find_similar_keys(key_name)
    if matches:
        return f"Did you mean one of these? {matches}"
    else:
        return "No similar keys found."

@mcp.tool()
def read_image(file_path: str) -> str:
    """
    Read an image file from the mounted device and return it as a JSON string with base64 encoded content.
    Supports standard images (JPG, PNG) and automatically converts HEIC to JPEG.
    
    IMPORTANT: Resizes the image to keep the payload small for LLM consumption.
    
    Output Format:
    {
        "type": "image",
        "data": "BASE64_STRING",
        "mimeType": "image/jpeg"
    }
    """
    import base64
    import subprocess
    import tempfile
    import json
    import mimetypes
    
    # Security check: ensure path is within mount point
    if not file_path.startswith(MOUNT_POINT):
        return "Access denied: File is outside the mount point."
        
    if not os.path.exists(file_path):
        return "File not found."
        
    try:
        # Always use a temp file for resizing
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # Use sips to resize and convert to JPEG
            # -Z 128: Resample height and width to max 128px
            # -s format jpeg: Output as JPEG
            cmd = ["sips", "-Z", "1024", "-s", "format", "jpeg", file_path, "--out", tmp_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return f"Error processing image: {result.stderr}"
                
            with open(tmp_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            mime_type = "image/jpeg"
                
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # Construct JSON response
        response = {
            "type": "image",
            "data": encoded_string,
            "mimeType": mime_type
        }
        return json.dumps(response)
            
    except Exception as e:
        return f"Error reading image: {e}"


@mcp.tool()
def check_db_status() -> str:
    """
    Check the status of the database connection.
    Returns "Connected" if successful, or an error message.
    """
    try:
        if db.check_connection():
            return "Connected"
        else:
            return "Disconnected: Health check failed."
    except Exception as e:
        return f"Disconnected: {e}"

@mcp.tool()
def check_mount_status() -> str:
    """
    Check the status of the file system mount point.
    Returns "Mounted" if successful, "Not Mounted" if not, or an error message.
    """
    try:
        if os.path.ismount(MOUNT_POINT):
            # Additional check: try to list directory to ensure it's readable
            try:
                os.listdir(MOUNT_POINT)
                return "Mounted and Readable"
            except PermissionError:
                return "Mounted but Permission Denied"
            except OSError as e:
                return f"Mounted but Error Accessing: {e}"
        else:
            if os.path.exists(MOUNT_POINT):
                return "Not Mounted (Directory exists)"
            else:
                return "Not Mounted (Directory does not exist)"
    except Exception as e:
        return f"Error checking mount status: {e}"

@mcp.tool()
def count_files(criteria: str = None) -> str:
    """
    Count files matching the criteria.
    Input can be a JSON string with "query" (semantic) and/or "where" (filter).
    Or just a simple string for semantic search if it's not valid JSON.
    
    Examples:
    - "mountains" (Semantic count)
    - {"Model": "iPhone 12"} (Exact filter count)
    - {"query": "mountains", "where": {"Model": "iPhone 12"}} (Combined)
    """
    import json
    query = None
    where = None
    
    if criteria:
        try:
            data = json.loads(criteria)
            if isinstance(data, dict):
                query = data.get("query")
                where = data.get("where")
                # If neither query nor where are keys, assume the whole dict is a filter
                if query is None and where is None:
                    where = data
            else:
                # If JSON but not dict (e.g. list), treat as query string
                query = str(data)
        except json.JSONDecodeError:
            # Not JSON, treat as semantic query
            query = criteria
            
    count = db.count_files(query=query, where=where)
    return str(count)

@mcp.tool()
def group_files(field: str, criteria: str = None) -> str:
    """
    Group files by a metadata field and return counts.
    Useful for getting a breakdown of files (e.g. by 'Model', 'CreationDate', 'Extension').
    
    Args:
        field: The metadata field to group by (e.g. "Model", "ext").
        criteria: Optional JSON string for filtering before grouping.
    """
    import json
    query = None
    where = None
    
    if criteria:
        try:
            data = json.loads(criteria)
            if isinstance(data, dict):
                query = data.get("query")
                where = data.get("where")
                if query is None and where is None:
                    where = data
            else:
                query = str(data)
        except json.JSONDecodeError:
            query = criteria
            
    groups = db.group_files_by_field(field=field, query=query, where=where)
    return str(groups)

@mcp.tool()
def get_database_summary() -> str:
    """
    Get a summary of the database statistics (total files, etc).
    """
    stats = db.get_database_stats()
    return str(stats)


@mcp.tool()
def run_advanced_query(criteria: str) -> str:
    """
    Run a complex query on the file database with support for filtering, semantic search, sorting, pagination, and projection.
    
    Args:
        criteria: A JSON string containing the query parameters.
    
    JSON Structure:
    {
        "query": "semantic search text" (Optional),
        "where": { ... } (Optional, Chroma/MongoDB style filter),
        "sort_by": "MetadataField" (Optional, e.g. "CreationDate", "Size"),
        "sort_order": "asc" or "desc" (Optional, default "asc"),
        "limit": 10 (Optional, default 10),
        "offset": 0 (Optional, default 0),
        "projection": ["Field1", "Field2"] (Optional, list of fields to return)
    }
    
    Examples:
    1. Find photos of mountains, sorted by date (newest first):
       {
         "query": "photos of mountains",
         "sort_by": "CreationDate",
         "sort_order": "desc"
       }
       
    2. Find all iPhone 12 photos, return only path and date:
       {
         "where": {"Model": "iPhone 12"},
         "projection": ["CreationDate"]
       }
       
    3. Pagination (Get page 2, 20 items per page):
       {
         "where": {"Model": "iPhone 12"},
         "limit": 20,
         "offset": 20
       }
    """
    import json
    try:
        data = json.loads(criteria)
    except json.JSONDecodeError:
        return "Error: Input must be a valid JSON string."
        
    if not isinstance(data, dict):
        return "Error: Input must be a JSON object."
        
    try:
        results = db.advanced_query(
            query=data.get("query"),
            where=data.get("where"),
            sort_by=data.get("sort_by"),
            sort_order=data.get("sort_order", "asc"),
            limit=data.get("limit", 10),
            offset=data.get("offset", 0),
            projection=data.get("projection")
        )
        return str(results)
    except Exception as e:
        return f"Error executing query: {e}"


@mcp.tool()
def run_aggregation_pipeline(pipeline: str) -> str:
    """
    Run a multi-stage aggregation pipeline for complex data processing.
    Modeled after MongoDB's aggregation framework.
    
    Args:
        pipeline: A JSON string representing a list of pipeline stages.
        
    Supported Stages & Syntax:
    
    1. **$match**: Filters documents (like SQL WHERE).
       - Syntax: `{"$match": { "Field": "Value", "Field2": { "$gt": 10 } }}`
       - Operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$and`, `$or`.
       - Special: Use `{"query": "search text"}` for semantic search.
       
    2. **$group**: Groups documents by `_id` and calculates accumulators.
       - Syntax: `{"$group": { "_id": "$FieldToGroupBy", "new_field": { "$accumulator": "$FieldToAccumulate" } }}`
       - Use `_id: null` to calculate stats for the entire dataset.
       - Accumulators: 
         - `$sum`: Sums values (use 1 to count).
         - `$avg`: Averages values.
         - `$min` / `$max`: Finds min/max values.
         - `$push`: Creates a list of values.
         - `$first`: Takes the first value (useful after sorting).
         
    3. **$project**: Reshapes documents (like SQL SELECT).
       - Use to keep only specific fields, rename fields, or remove fields.
       - Syntax (Inclusion): `{"$project": { "KeepField": 1, "RenameField": "$OldName" }}`
       - Syntax (Exclusion): `{"$project": { "RemoveField": 0 }}`
       
    4. **$sort**: Sorts documents (like SQL ORDER BY).
       - Syntax: `{"$sort": { "Field": 1 }}` (1 for Ascending, -1 for Descending).
       
    5. **$limit** / **$skip**: Pagination.
       - Syntax: `{"$limit": 10}`, `{"$skip": 5}`.
       
    6. **$count**: Counts results and outputs a single document.
       - Syntax: `{"$count": "output_field_name"}`.
    
    Examples:
    
    **Example 1: Filter and Count**
    "Count how many Apple devices have ISO > 100"
    ```json
    [
      {"$match": {"Make": "Apple", "ISO": {"$gt": 100}}},
      {"$count": "total_high_iso_apple"}
    ]
    ```
       
    **Example 2: Grouping and Statistics**
    "Get average ISO and total count for each Camera Model"
    ```json
    [
      {"$group": {
        "_id": "$Model", 
        "avg_iso": {"$avg": "$ISO"},
        "total": {"$sum": 1}
      }}
    ]
    ```
       
    **Example 3: Complex Pipeline (Filter -> Group -> Filter Groups -> Sort -> Project)**
    "Find models with avg ISO > 200, sort by count desc, and show only Model and Count"
    ```json
    [
      {"$match": {"Make": "Apple"}},
      {"$group": {
        "_id": "$Model", 
        "avg_iso": {"$avg": "$ISO"},
        "count": {"$sum": 1}
      }},
      {"$match": {"avg_iso": {"$gt": 200}}},
      {"$sort": {"count": -1}},
      {"$project": {"Model": "$_id", "count": 1, "_id": 0}}
    ]
    ```
    """
    import json
    try:
        pipeline_data = json.loads(pipeline)
    except json.JSONDecodeError:
        return "Error: Pipeline must be a valid JSON string."
        
    if not isinstance(pipeline_data, list):
        return "Error: Pipeline must be a list of stages."
        
    try:
        results = db.aggregate(pipeline_data)
        return str(results)
    except Exception as e:
        return f"Error executing pipeline: {e}"


if __name__ == "__main__":
    mcp.run()
