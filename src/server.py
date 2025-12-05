from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any
from mcp.server.fastmcp.utilities.types import Image
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
        
        # Callback to insert data as soon as it is processed
        def insert_chunk(chunk: List[Dict[str, Any]]):
            if chunk:
                db.upsert_files(chunk)
                print(f"Inserted chunk of {len(chunk)} files")

        metadata_list = scan_photos(MOUNT_POINT, existing_files=existing_files, callback=insert_chunk)
    except Exception as e:
        return f"Error scanning photos: {e}"
        
    # 3. Final Report
    if metadata_list:
        # Note: upsert_files is now called incrementally via callback.
        # We might want to do a final upsert if any were missed, but callback handles all.
        return f"Successfully indexed {len(metadata_list)} new files. (Skipped {len(existing_files)})"
    else:
        return f"No new files found. (Already cached {len(existing_files)})"

@mcp.tool()
def search_files(query: str, n_results: int = 10) -> str:
    """
    Search for files using metadata values without mentioning keys.
    n_results is the number of results to return. If not needed pass None.
    Note: Use filter_files() tool for precise location filtering using metadata key and value.

    Examples:
    - "Singapore photos" → Finds files with "Singapore" in metadata
    - "Photos taken in Singapore" → Better to use filter_files with GPS coordinates

    IMPORTANT RESTRICTIONS:
    1. This search is based on METADATA ONLY (filenames, dates, location, camera settings, etc.).
    2. It DOES NOT analyze the visual content of images. It cannot "see" the image.
    3. Queries like "photo of a dog" will only work if "dog" is explicitly mentioned in the metadata (e.g. filename 'dog.jpg' or UserComment).
    4. Available metadata includes: EXIF (Camera, Lens, ISO), Composite (GPS, ShutterSpeed), MakerNotes, IPTC, and XMP. Call get_metadata_keys() to see all available metadata keys in DB. 
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
    Call get_metadata_keys() to see all available metadata keys in DB.

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
def get_metadata_categories() -> str:
    """
    Get a list of available metadata categories (prefixes).
    Example output: ['EXIF', 'IPTC', 'XMP', 'General']
    Use this first to see what kind of metadata is available.
    """
    keys = db.get_cached_keys(category=None)
    return str(keys)

@mcp.tool()
def get_metadata_keys(category: str = None, refresh: bool = False) -> str:
    """
    Get available metadata keys.
    
    Args:
        category: Optional. If provided, returns keys for that category (e.g. "EXIF").
                  If None (default), returns a list of available CATEGORIES (prefixes).
        refresh: Optional. If True, forces a re-scan of the database to update the cache.
        
    Usage:
    1. Call `get_metadata_categories()` to see available categories.
    2. Call `get_metadata_keys(category='EXIF')` to see all EXIF keys.
    """
    keys = db.get_cached_keys(category=category, refresh=refresh)
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
def read_image(file_path: str) -> Image:
    """
    Read an image file from the mounted device.
    """
    
    # Security check: ensure path is within mount point
    if not file_path.startswith(MOUNT_POINT):
        raise ValueError("Access denied: File is outside the mount point.")
        
    if not os.path.exists(file_path):
        raise ValueError("File not found.")
        
    return Image(path=file_path)


@mcp.tool()
def copy_files_to_local(source_paths: List[str], destination_folder: str, new_filenames: List[str] = None) -> str:
    """
    Copy multiple files from the mounted device to a local destination folder.
    
    Args:
        source_paths: List of absolute paths to files on the mounted device.
        destination_folder: Local folder to copy files into.
        new_filenames: Optional. List of new filenames corresponding to source_paths. 
                       Must have same length as source_paths if provided.
    """
    import shutil
    
    # Validation for rename
    if new_filenames:
        if len(source_paths) != len(new_filenames):
            return f"Error: Mismatch in number of files. Source: {len(source_paths)}, New Names: {len(new_filenames)}"

    # Ensure destination folder exists
    if not os.path.exists(destination_folder):
        try:
            os.makedirs(destination_folder, exist_ok=True)
        except Exception as e:
            return f"Error creating destination folder: {e}"
            
    success_count = 0
    errors = []
    
    # Create an iterator for new_filenames if it exists, else use None
    # We use enumerate to get index for new_filenames access if needed, 
    # but zip is cleaner if we handle the None case.
    
    for i, src in enumerate(source_paths):
        if not src.startswith(MOUNT_POINT):
            errors.append(f"{src}: Access denied (outside mount point)")
            continue
            
        if not os.path.exists(src):
            errors.append(f"{src}: File not found")
            continue
            
        try:
            # Determine destination path
            if new_filenames:
                dest_filename = new_filenames[i]
                dest_path = os.path.join(destination_folder, dest_filename)
            else:
                filename = os.path.basename(src)
                dest_path = os.path.join(destination_folder, filename)
            
            shutil.copy2(src, dest_path)
            success_count += 1
        except Exception as e:
            errors.append(f"{src}: {str(e)}")
            
    if not errors:
        return f"Successfully copied all {success_count} files to {destination_folder}"
    else:
        error_msg = "\n".join(errors)
        return f"Copied {success_count}/{len(source_paths)} files.\nErrors:\n{error_msg}"


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

    NOTE: Semantic count ("query") is based on METADATA similarity, not visual content.
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

    IMPORTANT: "query" uses semantic search on METADATA ONLY. It cannot find objects inside images unless they are described in the metadata.

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
