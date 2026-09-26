"""Input/output contract validation for Agent OS."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.errors import ValidationError


def validate_input(schema: Optional[Dict[str, Any]], data: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal required-fields schema: {"required": ["a","b"], "properties": {...}}."""
    if not schema:
        return data
    required = schema.get("required") or []
    missing = [f for f in required if f not in data or data[f] is None or data[f] == ""]
    if missing:
        raise ValidationError(f"Missing required input fields: {missing}", details={"missing": missing})
    return data


def validate_output(schema: Optional[Dict[str, Any]], data: Any) -> Any:
    if not schema:
        return data
    if not isinstance(data, dict):
        raise ValidationError("Output must be an object")
    required = schema.get("required") or []
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(f"Missing required output fields: {missing}", details={"missing": missing})
    return data


# Default contracts for common capabilities
DEFAULT_INPUT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "research": {"required": ["query"], "properties": {"query": {"type": "string"}}},
    "financial_analysis": {"required": ["metrics"], "properties": {"metrics": {"type": "object"}}},
}

DEFAULT_OUTPUT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "research": {"required": ["findings"], "properties": {"findings": {"type": "array"}}},
    "financial_analysis": {"required": ["analysis"], "properties": {"analysis": {"type": "object"}}},
}
