"""Business report generator — HTML, Markdown, JSON (PDF/DOCX adapters ready)."""

from datetime import datetime
from typing import Any, Dict, Optional

from schemas.common import new_id


def generate_markdown_report(
    title: str,
    sections: Dict[str, Any],
    report_type: str = "management",
) -> str:
    lines = [
        f"# {title}",
        "",
        f"*Generated: {datetime.utcnow().isoformat()}Z*",
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
        if isinstance(val, str):
            lines.append(val)
        elif isinstance(val, list):
            for item in val:
                lines.append(f"- {item}")
        elif isinstance(val, dict):
            for k, v in val.items():
                lines.append(f"- **{k}**: {v}")
        else:
            lines.append(str(val))
        lines.append("")
    return "\n".join(lines)


def generate_json_report(title: str, sections: Dict[str, Any], report_type: str = "management") -> Dict[str, Any]:
    return {
        "report_id": new_id("RPT-"),
        "title": title,
        "report_type": report_type,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sections": sections,
    }


def generate_html_report(title: str, sections: Dict[str, Any], report_type: str = "management") -> str:
    md = generate_markdown_report(title, sections, report_type)
    # Minimal HTML wrapper — production can use a proper Markdown→HTML pipeline
    body = md.replace("\n", "<br>\n")
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
    h1, h2 {{ color: #1a1a2e; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
