from typing import Dict, Any, List, Set, Tuple
import json
from collections.abc import Mapping, Sequence


def flatten_json(obj: Any, parent_key: str = '', separator: str = '.') -> Dict[str, Any]:
    """
    Flatten nested JSON object into dot notation paths.
    
    Example:
        {'a': {'b': 1, 'c': [2, 3]}} -> 
        {'a.b': 1, 'a.c[0]': 2, 'a.c[1]': 3}
    """
    items: Dict[str, Any] = {}
    
    if obj is None:
        return items
    
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            items.update(flatten_json(value, new_key, separator))
    
    elif isinstance(obj, Sequence) and not isinstance(obj, str):
        for i, value in enumerate(obj):
            new_key = f"{parent_key}[{i}]"
            items.update(flatten_json(value, new_key, separator))
    
    else:
        items[parent_key] = obj
    
    return items


def compare_json_objects(obj1: Dict[str, Any], obj2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two JSON objects and return detailed differences.
    
    Returns structure with:
        - added: paths present in obj2 but not in obj1
        - removed: paths present in obj1 but not in obj2
        - changed: paths with different values (with old and new values)
        - unchanged: paths with same values
    """
    # Flatten both objects
    flat1 = flatten_json(obj1)
    flat2 = flatten_json(obj2)
    
    paths1 = set(flat1.keys())
    paths2 = set(flat2.keys())
    
    # Find changes
    added = paths2 - paths1
    removed = paths1 - paths2
    common = paths1 & paths2
    
    # Check changed values
    changed = set()
    unchanged = set()
    
    for path in common:
        # Compare JSON-serialized values to handle different types properly
        val1 = flat1[path]
        val2 = flat2[path]
        
        # Use JSON serialization for deep comparison
        if json.dumps(val1, sort_keys=True) != json.dumps(val2, sort_keys=True):
            changed.add(path)
        else:
            unchanged.add(path)
    
    # Build result structure with details
    result = {
        "added": sorted(list(added)),
        "removed": sorted(list(removed)),
        "changed": sorted(list(changed)),
        "unchanged": sorted(list(unchanged)),
        "details": {}
    }
    
    # Add details for added paths
    for path in added:
        result["details"][path] = {
            "new": flat2[path]
        }
    
    # Add details for removed paths
    for path in removed:
        result["details"][path] = {
            "old": flat1[path]
        }
    
    # Add details for changed values
    for path in changed:
        result["details"][path] = {
            "old": flat1[path],
            "new": flat2[path]
        }
    
    return result


def format_comparison_for_response(
    doc1: Any,
    doc2: Any,
    diff_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Format diff result into list of changes for API response.
    """
    changes = []
    
    # Added paths
    for path in diff_result["added"]:
        changes.append({
            "path": path,
            "type": "added",
            "value": {"new": diff_result["details"].get(path, {}).get("new")}
        })
    
    # Removed paths
    for path in diff_result["removed"]:
        changes.append({
            "path": path,
            "type": "removed",
            "value": {"old": diff_result["details"].get(path, {}).get("old")}
        })
    
    # Changed paths
    for path in diff_result["changed"]:
        changes.append({
            "path": path,
            "type": "changed",
            "value": {
                "old": diff_result["details"][path]["old"],
                "new": diff_result["details"][path]["new"]
            }
        })
    
    return changes