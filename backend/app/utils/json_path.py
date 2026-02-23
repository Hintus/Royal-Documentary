import re
from typing import Any, Dict, List, Union, Optional
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

def parse_json_path(path: str) -> List[Union[str, int]]:
    """
    Parse JSON path string into list of keys.
    
    Examples:
        "customer.name" -> ["customer", "name"]
        "addresses[0].city" -> ["addresses", 0, "city"]
        "settings.notifications[1].enabled" -> ["settings", "notifications", 1, "enabled"]
    """
    if not path:
        return []
    
    parts = []
    # Split by dots, but handle array indices
    for part in path.split('.'):
        # Check for array index like "addresses[0]"
        array_match = re.match(r'^(.+)\[(\d+)\]$', part)
        if array_match:
            key = array_match.group(1)
            index = int(array_match.group(2))
            parts.append(key)
            parts.append(index)
        else:
            parts.append(part)
    
    return parts


def get_value_at_path(obj: Any, path_parts: List[Union[str, int]]) -> Any:
    """
    Get value from nested object at specified path.
    
    Args:
        obj: The JSON object (dict/list)
        path_parts: List of keys/indices from parse_json_path
        
    Returns:
        Value at path
        
    Raises:
        KeyError: if path doesn't exist (not HTTPException!)
    """
    current = obj
    
    for i, part in enumerate(path_parts):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"Path not found at '{'.'.join(str(p) for p in path_parts[:i+1])}'")
            current = current[part]
        elif isinstance(current, list):
            if not isinstance(part, int):
                raise KeyError(f"Cannot use string key '{part}' on array")
            if part < 0 or part >= len(current):
                raise KeyError(f"Array index {part} out of bounds (length: {len(current)})")
            current = current[part]
        else:
            raise KeyError(f"Path not found at '{'.'.join(str(p) for p in path_parts[:i])}' (leaf node)")
    
    return current

def set_value_at_path(obj: Dict, path_parts: List[Union[str, int]], value: Any) -> Dict:
    """
    Set value in nested object at specified path.
    Modifies the original object in place.
    """
    if not path_parts:
        return value

    current = obj

    # Navigate to parent of target
    for i, part in enumerate(path_parts[:-1]):
        if isinstance(current, dict):
            if part not in current:
                # Create missing intermediate objects
                next_part = path_parts[i + 1]
                if isinstance(next_part, int):
                    current[part] = []  # создаём массив, если следующий индекс
                else:
                    current[part] = {}  # создаём объект, если следующий ключ
            current = current[part]
        elif isinstance(current, list):
            if not isinstance(part, int):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot use string key '{part}' on array"
                )
            # Extend list if needed
            while len(current) <= part:
                current.append(None)
            current = current[part]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot navigate through leaf node"
            )

    # Set the value at final key
    final_key = path_parts[-1]

    if isinstance(current, dict):
        current[final_key] = value
    elif isinstance(current, list):
        if not isinstance(final_key, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot use string key '{final_key}' on array"
            )
        while len(current) <= final_key:
            current.append(None)
        current[final_key] = value

    return obj

def delete_value_at_path(obj: Dict, path_parts: List[Union[str, int]]) -> Dict:
    """Delete value from nested object at specified path."""
    logger.info(f"DELETE - Starting with obj: {obj}")
    logger.info(f"DELETE - Path parts: {path_parts}")
    
    if not path_parts:
        return {}
    
    current = obj
    
    # Navigate to parent
    for i, part in enumerate(path_parts[:-1]):
        logger.info(f"DELETE - Navigating: level {i}, part {part}, current type {type(current)}")
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"Path not found at '{'.'.join(str(p) for p in path_parts[:i+1])}'")
            current = current[part]
        elif isinstance(current, list):
            if not isinstance(part, int):
                raise KeyError(f"Cannot use string key '{part}' on array")
            if part < 0 or part >= len(current):
                raise KeyError(f"Array index {part} out of bounds")
            current = current[part]
        else:
            raise KeyError(f"Cannot navigate through leaf node")
    
    # Delete at final key
    final_key = path_parts[-1]
    logger.info(f"DELETE - Final key: {final_key}, current type: {type(current)}")
    
    if isinstance(current, dict):
        logger.info(f"DELETE - Deleting from dict: key {final_key}")
        if final_key not in current:
            raise KeyError(f"Key '{final_key}' not found")
        del current[final_key]
    elif isinstance(current, list):
        logger.info(f"DELETE - Deleting from list: index {final_key}")
        if not isinstance(final_key, int):
            raise KeyError(f"Cannot use string key '{final_key}' on array")
        if final_key < 0 or final_key >= len(current):
            raise KeyError(f"Array index {final_key} out of bounds")
        # Правильное удаление элемента массива
        logger.info(f"DELETE - Before deletion: {current}")
        del current[final_key]
        logger.info(f"DELETE - After deletion: {current}")
    else:
        logger.info(f"DELETE - Unexpected type: {type(current)}")
    
    logger.info(f"DELETE - Result obj: {obj}")
    return obj