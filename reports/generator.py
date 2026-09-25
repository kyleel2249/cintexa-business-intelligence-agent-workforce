"""Business report generator — HTML, Markdown, JSON (PDF/DOCX adapters ready)."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from schemas.common import new_id


def _json_safe(value: Any) -> Any:
    """Recursively convert enums / non-JSON-native values to plain strings."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _render_value(val: Any) -> str:
    """Render a section value for the Markdown report body, human-readably."""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        if not val:
            return "_None._"
        return "\n".join(f"- {_render_value(item)}" for item in val)
    if isinstance(val, dict):
        if not val:
            return "_None._"
        safe = _json_safe(val)
        return "```json\n" + json.dumps(safe, indent=2, ensure_ascii=False) + "\n```"
    return str(val)


def generate_markdown_report(
    title: str,
    sections: Dict[str, Any],
    report_type: str = "management",
) -> str:
    lines = [
        f"# {title}",
        "",
        f"*Generated: {datetime.now(timezone.utc).isoformat()}Z*",
        f"*Report type: {report_type}*",
        "",
        "---",
        "",
    ]
    order = [
        "executive_summary",
        "objective",
        "data_used",
        "methodology",
        "findings",
        "evidence",
        "key_metrics",
        "risks",
        "opportunities",
        "assumptions",
        "uncertainties",
        "recommendations",
        "action_plan",
        "sources",
        "confidence",
    ]
    for key in order:
        if key not in sections:
            continue
        val = sections[key]
        heading = key.replace("_", " ").title()
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(_render_value(val))
        lines.append("")
    return "\n".join(lines)


def generate_json_report(title: str, sections: Dict[str, Any], report_type: str = "management") -> Dict[str, Any]:
    return {
        "report_id": new_id("RPT-"),
        "title": title,
        "report_type": report_type,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "sections": _json_safe(sections),
    }


def generate_html_report(title: str, sections: Dict[str, Any], report_type: str = "management") -> str:
    md = generate_markdown_report(title, sections, report_type)
    try:
        import markdown as _markdown
        body = _markdown.markdown(md, extensions=["fenced_code", "tables"])
    except ImportError:
        # Fallback if the optional 'markdown' package isn't installed.
        body = md.replace("\n", "<br>\n")
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #1a1a2e; }}
    h1, h2 {{ color: #1a1a2e; }}
    pre {{ background: #f4f5f7; padding: 0.85rem 1rem; border-radius: 8px; overflow-x: auto; }}
    code {{ font-family: ui-monospace, "JetBrains Mono", monospace; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
