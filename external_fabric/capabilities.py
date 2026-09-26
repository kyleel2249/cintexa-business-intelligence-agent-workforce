"""External interaction capability registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExternalCapability:
    capability_id: str
    name: str
    risk_level: str  # READ|LOW|MEDIUM|HIGH|CRITICAL
    required_permissions: List[str] = field(default_factory=list)
    requires_approval: bool = False
    reversible: bool = True
    destructive: bool = False
    rate_key: Optional[str] = None


CAPABILITIES: Dict[str, ExternalCapability] = {}


def _reg(c: ExternalCapability) -> None:
    CAPABILITIES[c.capability_id] = c


for cid, name, risk, perms, approval in [
    ("WEB_OPEN_URL", "Open URL", "READ", ["web:read"], False),
    ("WEB_READ_PAGE", "Read page", "READ", ["web:read"], False),
    ("WEB_EXTRACT_DATA", "Extract data", "READ", ["web:read"], False),
    ("WEB_SEARCH", "Web search", "READ", ["web:search"], False),
    ("WEB_RESEARCH", "Web research", "READ", ["web:research"], False),
    ("WEB_SCREENSHOT", "Screenshot", "READ", ["web:read"], False),
    ("WEB_DOWNLOAD", "Download", "LOW", ["web:download"], False),
    ("WEB_CLICK", "Click", "LOW", ["web:interact"], False),
    ("WEB_FILL_FORM", "Fill form", "MEDIUM", ["web:form"], True),
    ("WEB_SUBMIT_FORM", "Submit form", "HIGH", ["web:form"], True),
    ("MEDIA_VIEW", "View media", "READ", ["media:read"], False),
    ("VIDEO_TRANSCRIPTION", "Transcribe video", "READ", ["media:analyze"], False),
    ("IMAGE_ANALYSIS", "Analyze image", "READ", ["media:analyze"], False),
    ("SOCIAL_READ", "Social read", "READ", ["social:read"], False),
    ("SOCIAL_LIKE", "Like", "LOW", ["social:react"], False),
    ("SOCIAL_COMMENT", "Comment", "MEDIUM", ["social:comment"], True),
    ("SOCIAL_REPLY", "Reply", "MEDIUM", ["social:comment"], True),
    ("SOCIAL_FOLLOW", "Follow", "MEDIUM", ["social:follow"], True),
    ("SOCIAL_MESSAGE", "Message", "HIGH", ["social:message"], True),
    ("CONTENT_PUBLICATION", "Publish", "HIGH", ["social:publish"], True),
    ("BUSINESS_TRANSACTION", "Transaction", "CRITICAL", ["business:transact"], True),
]:
    _reg(
        ExternalCapability(
            capability_id=cid,
            name=name,
            risk_level=risk,
            required_permissions=perms,
            requires_approval=approval,
            rate_key=cid.lower(),
            destructive=risk in ("HIGH", "CRITICAL"),
            reversible=risk not in ("CRITICAL",),
        )
    )


def get_capability(capability_id: str) -> Optional[ExternalCapability]:
    return CAPABILITIES.get(capability_id)
