import chromadb
from chromadb.config import Settings
import json
import os
from typing import List, Dict, Any, Set

class Database:
    def __init__(self, db_path: str = "/Users/harsha/GitProjects/ios_mcp/chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="files")

    def upsert_files(self, metadata_list: List[Dict[str, Any]]):
        """
        Batch insert or update file metadata.
        """
        if not metadata_list:
            return

        ids = []
        documents = []
        metadatas = []

        for meta in metadata_list:
            path = meta.get('SourceFile')
            if path:
                ids.append(path)
                # Create a string representation for semantic search
                # We include key fields like Model, Date, Location if available
                # Or just dump the whole JSON as the document content
                doc_str = f"File: {os.path.basename(path)}\n"
                for k, v in meta.items():
                    if k not in ['SourceFile', 'Directory', 'FilePermissions']: # Skip technical fields
                        doc_str += f"{k}: {v}\n"
                documents.append(doc_str)
                
                # Chroma metadata values must be str, int, float, or bool. 
                # It doesn't support nested dicts or lists in metadata.
                # We need to flatten or filter metadata.
                clean_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    else:
                        clean_meta[k] = str(v) # Convert complex types to string
                metadatas.append(clean_meta)

        if ids:
            # Chroma handles batching automatically, but for very large sets we might want to chunk
            # Default batch size is usually fine for < 40k items
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

    def query_files(self, query: str = None, where: Dict[str, Any] = None, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search files.
        - If `query` is provided: Performs semantic search (nearest neighbors), optionally filtered by `where`.
        - If only `where` is provided: Performs exact filtering (e.g., {'Model': 'iPhone 12'}).
        - Provide n_results on how many output results you want. If not needed pass None.
        """
        if not query and not where:
            return []

        output = []
        
        if query:
            # Semantic search with optional filter
            results = self.collection.query(
                query_texts=[query],
                where=where,
                n_results=n_results
            )
            # Process semantic results
            if results['metadatas'] and len(results['metadatas']) > 0:
                 for i, meta in enumerate(results['metadatas'][0]):
                     meta['SourceFile'] = results['ids'][0][i]
                     meta['score'] = results['distances'][0][i]
                     output.append(meta)
        else:
            # Exact filtering only (no semantic search)
            results = self.collection.get(
                where=where,
                limit=n_results
            )
            # Process filter results
            if results['metadatas']:
                for i, meta in enumerate(results['metadatas']):
                    meta['SourceFile'] = results['ids'][i]
                    output.append(meta)

        return output

    def get_all_files(self) -> List[Dict[str, Any]]:
        """
        Get all files. Note: Chroma isn't optimized for "get all", 
        but we can use get() without ids.
        """
        results = self.collection.get()
        output = []
        if results['metadatas']:
            for i, meta in enumerate(results['metadatas']):
                meta['SourceFile'] = results['ids'][i]
                output.append(meta)
        return output

    def get_existing_files_map(self) -> Set[str]:
        """
        Returns a set of existing file paths.
        Used for incremental scanning.
        """
        # We just need IDs
        results = self.collection.get(include=[]) # Don't include embeddings or metadata
        return set(results['ids'])

    def clear_db(self):
        self.client.delete_collection("files")
        self.collection = self.client.get_or_create_collection(name="files")

    def get_all_keys(self) -> Set[str]:
        """
        Get all unique metadata keys (columns) present in the database.
        Note: This can be expensive as it iterates over all records.
        """
        keys = set()
        # Chroma doesn't have a schema, so we must scan.
        # Optimization: We could cache this set and update it on upsert.
        # For now, let's scan.
        results = self.collection.get(include=['metadatas'])
        if results['metadatas']:
            for meta in results['metadatas']:
                keys.update(meta.keys())
        return keys

    def find_similar_keys(self, search_key: str, n: int = 5) -> List[str]:
        """
        Find metadata keys similar to the search_key using fuzzy matching.
        Useful for correcting LLM hallucinations (e.g. 'CameraModel' -> 'Model').
        """
        import difflib
        all_keys = list(self.get_all_keys())
        # Get close matches
        matches = difflib.get_close_matches(search_key, all_keys, n=n, cutoff=0.4)
        return matches

    def check_connection(self) -> bool:
        """
        Check if the database is responsive.
        """
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False

    def count_files(self, query: str = None, where: Dict[str, Any] = None) -> int:
        """
        Count files matching the criteria.
        """
        if not query and not where:
            return self.collection.count()
        
        if query:
            # Semantic search count is tricky because query() returns top N results.
            # We can't easily get a "total count" of semantic matches without retrieving all.
            # However, for this use case, if a query is provided, we usually want to know 
            # how many "relevant" items there are. 
            # Chroma doesn't support "count where query matches".
            # We will fetch a large number (limit) and count.
            # OR, if only 'where' is used, we can use get() with include=[]
            
            # If query is present, we are limited by n_results. 
            # Let's assume for 'count' with query, the user might want to know how many *strong* matches there are.
            # But standard DB count usually implies exact matches.
            
            # If the user mixes query (semantic) and where (filter), it's a semantic search.
            # We'll fetch up to 1000 results and count them.
            results = self.collection.query(
                query_texts=[query],
                where=where,
                n_results=1000 # Arbitrary limit for "count" in semantic search
            )
            return len(results['ids'][0]) if results['ids'] else 0
            
        else:
            # Exact filtering
            results = self.collection.get(
                where=where,
                include=[] # Don't fetch data, just IDs
            )
            return len(results['ids']) if results['ids'] else 0

    def group_files_by_field(self, field: str, query: str = None, where: Dict[str, Any] = None) -> Dict[str, int]:
        """
        Group files by a specific metadata field and return counts.
        Example: group_files_by_field('Model') -> {'iPhone 12': 10, 'iPhone 13': 5}
        """
        # 1. Fetch results
        if query:
             results = self.collection.query(
                query_texts=[query],
                where=where,
                n_results=2000 
            )
             metadatas = results['metadatas'][0] if results['metadatas'] else []
        else:
            # If no query, we can fetch all matching the filter
            results = self.collection.get(
                where=where,
                include=['metadatas']
            )
            metadatas = results['metadatas'] if results['metadatas'] else []

        # 2. Group in Python
        from collections import defaultdict
        groups = defaultdict(int)
        
        for meta in metadatas:
            val = meta.get(field)
            if val is not None:
                groups[str(val)] += 1
            else:
                groups['Unknown'] += 1
                
        return dict(groups)

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get general database statistics.
        """
        count = self.collection.count()
        # We could add more stats here if we tracked them (e.g. last scan time)
        return {
            "total_files": count,
            "collection_name": self.collection.name,
            # "db_path": self.client._path # Private attribute, might not be safe
        }


    def advanced_query(
        self,
        query: str = None,
        where: Dict[str, Any] = None,
        sort_by: str = None,
        sort_order: str = "asc",
        limit: int = 10,
        offset: int = 0,
        projection: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform a complex query with filtering, sorting, pagination, and projection.
        """
        # 1. Fetch Results
        if query:
            # Semantic search
            # We fetch more than limit if we need to sort by a metadata field later
            # But if we just rely on semantic score, we can use limit+offset
            fetch_limit = limit + offset
            if sort_by:
                # If sorting by metadata, we might need to fetch ALL matches to sort correctly
                # This is a limitation of Chroma + Post-processing.
                # For now, let's fetch a reasonable large batch (e.g. 1000) or all if possible?
                # Chroma query doesn't support "all".
                fetch_limit = 2000 # Arbitrary cap for performance
            
            results = self.collection.query(
                query_texts=[query],
                where=where,
                n_results=fetch_limit
            )
            
            items = []
            if results['metadatas'] and len(results['metadatas']) > 0:
                 for i, meta in enumerate(results['metadatas'][0]):
                     item = meta.copy()
                     item['SourceFile'] = results['ids'][0][i]
                     item['score'] = results['distances'][0][i]
                     items.append(item)
        else:
            # Exact filtering
            # If sorting is required, we must fetch ALL to sort in Python
            if sort_by:
                results = self.collection.get(where=where) # Fetch all
            else:
                # If no sort, we can rely on Chroma's internal order (undefined) + slice
                # But Chroma .get() supports limit/offset
                results = self.collection.get(
                    where=where,
                    limit=limit,
                    offset=offset
                )
            
            items = []
            if results['metadatas']:
                for i, meta in enumerate(results['metadatas']):
                    item = meta.copy()
                    item['SourceFile'] = results['ids'][i]
                    items.append(item)

        # 2. Sort (if needed)
        # Note: If query was present and sort_by is None, items are already sorted by score (distance)
        if sort_by:
            def get_sort_key(x):
                val = x.get(sort_by)
                # Handle types for correct sorting (e.g. numbers vs strings)
                # Try to convert to float if possible for numerical sort
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return str(val) if val is not None else ""

            reverse = (sort_order.lower() == "desc")
            items.sort(key=get_sort_key, reverse=reverse)
            
            # Apply pagination AFTER sorting (if we fetched all)
            # If we used semantic search, we already limited fetch, but we might need to slice again
            # if we fetched extra for sorting.
            if query:
                 # We fetched up to 2000. Now we slice the page.
                 start = offset
                 end = offset + limit
                 items = items[start:end]
            else:
                # We fetched ALL for exact filter + sort. Now slice.
                start = offset
                end = offset + limit
                items = items[start:end]

        # 3. Projection
        if projection:
            projected_items = []
            for item in items:
                new_item = {}
                # Always include SourceFile unless explicitly excluded? 
                # Usually DBs include ID. Let's include SourceFile.
                if 'SourceFile' in item:
                    new_item['SourceFile'] = item['SourceFile']
                
                for field in projection:
                    if field in item:
                        new_item[field] = item[field]
                projected_items.append(new_item)
            items = projected_items

        return items

    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute an aggregation pipeline.
        Supported stages: $match, $group, $sort, $project, $limit, $skip, $count.
        """
        if not pipeline:
            return []

        # Optimization: Check if the first stage is $match to use DB filtering
        first_stage = pipeline[0]
        initial_docs = []
        
        if "$match" in first_stage:
            # Use Chroma to fetch initial set
            match_criteria = first_stage["$match"]
            # Check if it's a semantic query or exact filter
            # We support a special "query" key in $match for semantic search, 
            # or just standard fields for filter.
            query_text = match_criteria.pop("query", None) if isinstance(match_criteria, dict) else None
            
            if query_text:
                # Semantic search
                results = self.collection.query(
                    query_texts=[query_text],
                    where=match_criteria if match_criteria else None,
                    n_results=2000 # Fetch a reasonable amount for aggregation
                )
                if results['metadatas'] and len(results['metadatas']) > 0:
                     for i, meta in enumerate(results['metadatas'][0]):
                         item = meta.copy()
                         item['SourceFile'] = results['ids'][0][i]
                         item['score'] = results['distances'][0][i]
                         initial_docs.append(item)
            else:
                # Exact filter
                results = self.collection.get(where=match_criteria)
                if results['metadatas']:
                    for i, meta in enumerate(results['metadatas']):
                        item = meta.copy()
                        item['SourceFile'] = results['ids'][i]
                        initial_docs.append(item)
            
            # Remove the first stage as we've processed it
            pipeline = pipeline[1:]
        else:
            # No initial match, fetch all (expensive!)
            results = self.collection.get()
            if results['metadatas']:
                for i, meta in enumerate(results['metadatas']):
                    item = meta.copy()
                    item['SourceFile'] = results['ids'][i]
                    initial_docs.append(item)

        current_docs = initial_docs

        for stage in pipeline:
            if "$match" in stage:
                current_docs = self._stage_match(current_docs, stage["$match"])
            elif "$group" in stage:
                current_docs = self._stage_group(current_docs, stage["$group"])
            elif "$sort" in stage:
                current_docs = self._stage_sort(current_docs, stage["$sort"])
            elif "$project" in stage:
                current_docs = self._stage_project(current_docs, stage["$project"])
            elif "$limit" in stage:
                limit = stage["$limit"]
                current_docs = current_docs[:limit]
            elif "$skip" in stage:
                skip = stage["$skip"]
                current_docs = current_docs[skip:]
            elif "$count" in stage:
                count_field = stage["$count"]
                current_docs = [{count_field: len(current_docs)}]

        return current_docs

    def _stage_match(self, docs: List[Dict], criteria: Dict) -> List[Dict]:
        """
        Filter documents in memory.
        Supports simple equality and some operators ($gt, $lt, $in).
        """
        filtered = []
        for doc in docs:
            match = True
            for key, value in criteria.items():
                if key == "$or":
                    # Handle OR logic
                    if not any(self._check_condition(doc, sub_criteria) for sub_criteria in value):
                        match = False
                        break
                elif key == "$and":
                    if not all(self._check_condition(doc, sub_criteria) for sub_criteria in value):
                        match = False
                        break
                else:
                    # Standard field check
                    if not self._check_condition(doc, {key: value}):
                        match = False
                        break
            if match:
                filtered.append(doc)
        return filtered

    def _check_condition(self, doc: Dict, condition: Dict) -> bool:
        """
        Check if a document satisfies a single condition (key: value or key: {op: value}).
        """
        for key, expected in condition.items():
            actual = doc.get(key)
            
            if isinstance(expected, dict):
                # Operator check
                for op, op_val in expected.items():
                    if op == "$gt":
                        if not (actual is not None and actual > op_val): return False
                    elif op == "$gte":
                        if not (actual is not None and actual >= op_val): return False
                    elif op == "$lt":
                        if not (actual is not None and actual < op_val): return False
                    elif op == "$lte":
                        if not (actual is not None and actual <= op_val): return False
                    elif op == "$ne":
                        if actual == op_val: return False
                    elif op == "$in":
                        if actual not in op_val: return False
                    elif op == "$nin":
                        if actual in op_val: return False
            else:
                # Equality check
                if actual != expected:
                    return False
        return True

    def _stage_group(self, docs: List[Dict], spec: Dict) -> List[Dict]:
        """
        Group documents.
        spec: { "_id": "$Field", "count": { "$sum": 1 }, ... }
        """
        from collections import defaultdict
        
        id_expr = spec.get("_id")
        groups = defaultdict(list)
        
        # 1. Grouping
        for doc in docs:
            # Resolve _id value
            if id_expr and isinstance(id_expr, str) and id_expr.startswith("$"):
                field = id_expr[1:]
                group_key = doc.get(field)
            else:
                group_key = id_expr # Constant or None
            
            # Convert list/dict keys to string to be hashable
            if isinstance(group_key, (list, dict)):
                group_key = str(group_key)
                
            groups[group_key].append(doc)
            
        # 2. Accumulation
        output = []
        for key, group_docs in groups.items():
            result_doc = {"_id": key}
            
            for field, accumulator in spec.items():
                if field == "_id":
                    continue
                
                # accumulator is like {"$sum": 1} or {"$avg": "$Age"}
                for op, op_val in accumulator.items():
                    if op == "$sum":
                        if op_val == 1:
                            result_doc[field] = len(group_docs)
                        elif isinstance(op_val, str) and op_val.startswith("$"):
                            # Sum a field
                            target_field = op_val[1:]
                            # Try to convert to float for sum
                            total = 0
                            for d in group_docs:
                                val = d.get(target_field)
                                try:
                                    total += float(val)
                                except (ValueError, TypeError):
                                    continue
                            result_doc[field] = total
                    elif op == "$avg":
                        if isinstance(op_val, str) and op_val.startswith("$"):
                            target_field = op_val[1:]
                            values = []
                            for d in group_docs:
                                val = d.get(target_field)
                                try:
                                    values.append(float(val))
                                except (ValueError, TypeError):
                                    continue
                            result_doc[field] = sum(values) / len(values) if values else 0
                    elif op == "$min":
                        if isinstance(op_val, str) and op_val.startswith("$"):
                            target_field = op_val[1:]
                            values = []
                            for d in group_docs:
                                val = d.get(target_field)
                                try:
                                    values.append(float(val))
                                except (ValueError, TypeError):
                                    continue
                            result_doc[field] = min(values) if values else None
                    elif op == "$max":
                        if isinstance(op_val, str) and op_val.startswith("$"):
                            target_field = op_val[1:]
                            values = []
                            for d in group_docs:
                                val = d.get(target_field)
                                try:
                                    values.append(float(val))
                                except (ValueError, TypeError):
                                    continue
                            result_doc[field] = max(values) if values else None
                    elif op == "$push":
                        if isinstance(op_val, str) and op_val.startswith("$"):
                            target_field = op_val[1:]
                            result_doc[field] = [d.get(target_field) for d in group_docs]
                    elif op == "$first":
                         if isinstance(op_val, str) and op_val.startswith("$"):
                            target_field = op_val[1:]
                            result_doc[field] = group_docs[0].get(target_field) if group_docs else None
            
            output.append(result_doc)
            
        return output

    def _stage_sort(self, docs: List[Dict], spec: Dict) -> List[Dict]:
        """
        Sort documents.
        spec: { "Field": 1 } or { "Field": -1 }
        """
        # Python's sort is stable, so we can sort by multiple keys by sorting in reverse order of keys
        # But for simplicity, let's handle single key sort or simple multi-key
        
        # Convert spec to list of (key, direction)
        sort_keys = []
        for k, v in spec.items():
            sort_keys.append((k, v))
            
        # Sort
        # We'll use a custom key function
        def get_sort_key(item):
            values = []
            for k, _ in sort_keys:
                val = item.get(k)
                # Normalize for comparison (None is smallest)
                if val is None:
                    values.append((0, "")) # Type 0 for None
                elif isinstance(val, (int, float)):
                    values.append((1, val)) # Type 1 for numbers
                else:
                    values.append((2, str(val))) # Type 2 for strings
            return tuple(values)

        # Since Python sort key doesn't support mixed directions easily in one pass for complex types,
        # we will do a simple single-key sort or assume all same direction if we want to be lazy.
        # BUT, to do it right:
        # We can sort repeatedly.
        
        for k, direction in reversed(sort_keys):
            reverse = (direction == -1 or direction == "desc")
            docs.sort(key=lambda x: x.get(k) if x.get(k) is not None else "", reverse=reverse)
            
        return docs

    def _stage_project(self, docs: List[Dict], spec: Dict) -> List[Dict]:
        """
        Project fields.
        spec: { "Field": 1, "Other": 0 }
        """
        projected = []
        
        # Check if it's an inclusion or exclusion projection
        # Mixed is not allowed in Mongo usually, except for _id.
        # We'll assume inclusion if any field is 1.
        is_inclusion = any(v == 1 or v is True for k, v in spec.items() if k != "_id")
        
        for doc in docs:
            new_doc = {}
            if is_inclusion:
                # Inclusion mode: start empty, add specified
                # _id is included by default unless excluded
                if spec.get("_id") != 0 and "_id" in doc:
                    new_doc["_id"] = doc["_id"]
                    
                for k, v in spec.items():
                    if (v == 1 or v is True) and k in doc:
                        new_doc[k] = doc[k]
            else:
                # Exclusion mode: start with all, remove specified
                new_doc = doc.copy()
                for k, v in spec.items():
                    if (v == 0 or v is False) and k in new_doc:
                        del new_doc[k]
            projected.append(new_doc)
            
        return projected
