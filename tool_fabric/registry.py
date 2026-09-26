"""Persistent Tool Registry + discovery."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.errors import ConflictError, NotFoundError, ValidationError
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from tool_fabric.models_db import TFTool


BUILTIN_TOOLS = [
    {
        "slug": "file.read",
        "name": "Read File",
        "category": "files",
        "capabilities": ["read_file"],
        "permissions": ["READ_FILE"],
        "risk": "low",
        "input_schema": {"required": ["path"]},
        "description": "Read a file inside the execution workspace",
    },
    {
        "slug": "file.write",
        "name": "Write File",
        "category": "files",
        "capabilities": ["write_file"],
        "permissions": ["WRITE_FILE"],
        "risk": "medium",
        "input_schema": {"required": ["path", "content"]},
        "description": "Write a file inside the execution workspace",
    },
    {
        "slug": "file.list",
        "name": "List Files",
        "category": "files",
        "capabilities": ["list_files"],
        "permissions": ["READ_FILE"],
        "risk": "low",
        "input_schema": {"required": []},
        "description": "List files in workspace",
    },
    {
        "slug": "code.python",
        "name": "Python Execute",
        "category": "code",
        "capabilities": ["execute_code", "python"],
        "permissions": ["EXECUTE_CODE"],
        "risk": "high",
        "input_schema": {"required": ["code"]},
        "timeout_sec": 15,
        "description": "Run Python in isolated workspace",
    },
    {
        "slug": "code.javascript",
        "name": "JavaScript Execute",
        "category": "code",
        "capabilities": ["execute_code", "javascript"],
        "permissions": ["EXECUTE_CODE"],
        "risk": "high",
        "input_schema": {"required": ["code"]},
        "timeout_sec": 15,
        "description": "Run Node.js in isolated workspace",
    },
    {
        "slug": "shell.run",
        "name": "Shell Command",
        "category": "shell",
        "capabilities": ["execute_shell"],
        "permissions": ["EXECUTE_SHELL"],
        "risk": "critical",
        "input_schema": {"required": ["argv"]},
        "timeout_sec": 15,
        "description": "Run allowlisted argv (no shell interpolation)",
    },
    {
        "slug": "http.request",
        "name": "HTTP Request",
        "category": "http",
        "capabilities": ["network_access", "http"],
        "permissions": ["NETWORK_ACCESS"],
        "risk": "medium",
        "input_schema": {"required": ["url"]},
        "description": "Policy-controlled HTTP client",
    },
    {
        "slug": "git.status",
        "name": "Git Status",
        "category": "git",
        "capabilities": ["repository_read"],
        "permissions": ["READ_REPOSITORY"],
        "risk": "low",
        "input_schema": {"required": []},
        "description": "Git status in workspace repo",
    },
    {
        "slug": "git.clone",
        "name": "Git Clone",
        "category": "git",
        "capabilities": ["repository_read"],
        "permissions": ["READ_REPOSITORY", "NETWORK_ACCESS"],
        "risk": "medium",
        "input_schema": {"required": ["url"]},
        "requires_approval": False,
        "description": "Clone repository into workspace",
    },
    {
        "slug": "browser.open",
        "name": "Browser Open",
        "category": "browser",
        "capabilities": ["browser_access"],
        "permissions": ["BROWSER_ACCESS", "NETWORK_ACCESS"],
        "risk": "medium",
        "input_schema": {"required": ["url"]},
        "description": "Fetch and extract page content (controlled)",
    },
    {
        "slug": "deploy.apply",
        "name": "Deploy Apply",
        "category": "deployment",
        "capabilities": ["deploy_application"],
        "permissions": ["DEPLOY_APPLICATION"],
        "risk": "critical",
        "requires_approval": True,
        "input_schema": {"required": ["target"]},
        "description": "Protected deployment operation",
    },
]


class ToolRegistry:
    SYSTEM = "__system__"

    def register(
        self,
        *,
        organisation_id: str,
        slug: str,
        name: str,
        category: str,
        capabilities: List[str],
        permissions: Optional[List[str]] = None,
        version: str = "1.0.0",
        risk: str = "low",
        requires_approval: bool = False,
        input_schema: Optional[Dict] = None,
        description: str = "",
        timeout_sec: int = 30,
        enabled: bool = True,
    ) -> TFTool:
        with UnitOfWork() as uow:
            exists = (
                uow.session.query(TFTool)
                .filter_by(organisation_id=organisation_id, slug=slug, version=version)
                .one_or_none()
            )
            if exists:
                raise ConflictError(f"Tool {slug}@{version} already registered")
            tool = TFTool(
                tool_id=new_id("TOOL-"),
                organisation_id=organisation_id,
                name=name,
                slug=slug,
                description=description,
                version=version,
                category=category,
                capabilities=capabilities,
                permissions=permissions or [],
                risk=risk,
                requires_approval=requires_approval,
                input_schema=input_schema or {},
                timeout_sec=timeout_sec,
                enabled=enabled,
            )
            uow.session.add(tool)
            uow.session.flush()
            uow.session.expunge(tool)
            return tool

    def bootstrap_builtins(self, organisation_id: str = "__system__") -> int:
        n = 0
        for t in BUILTIN_TOOLS:
            try:
                self.register(organisation_id=organisation_id, **{k: v for k, v in t.items()})
                n += 1
            except ConflictError:
                pass
        return n

    def get(self, tool_id: str, organisation_id: str) -> Optional[TFTool]:
        with UnitOfWork() as uow:
            row = uow.session.get(TFTool, tool_id)
            if not row:
                return None
            if row.organisation_id not in (organisation_id, self.SYSTEM):
                return None
            uow.session.expunge(row)
            return row

    def get_by_slug(self, slug: str, organisation_id: str) -> Optional[TFTool]:
        with UnitOfWork() as uow:
            row = (
                uow.session.query(TFTool)
                .filter_by(slug=slug, enabled=True)
                .filter(TFTool.organisation_id.in_([organisation_id, self.SYSTEM]))
                .order_by(TFTool.organisation_id.desc())  # org-specific first roughly
                .first()
            )
            if row:
                uow.session.expunge(row)
            return row

    def discover(
        self,
        organisation_id: str,
        *,
        capability: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[TFTool]:
        with UnitOfWork() as uow:
            q = uow.session.query(TFTool).filter(
                TFTool.enabled == True,  # noqa: E712
                TFTool.organisation_id.in_([organisation_id, self.SYSTEM]),
            )
            if category:
                q = q.filter_by(category=category)
            rows = q.all()
            out = []
            for r in rows:
                if capability and capability not in (r.capabilities or []):
                    continue
                uow.session.expunge(r)
                out.append(r)
            return out

    def select(self, organisation_id: str, capability: str) -> Optional[TFTool]:
        tools = self.discover(organisation_id, capability=capability)
        tools = [t for t in tools if t.enabled]
        if not tools:
            return None
        tools.sort(key=lambda t: (-(t.health_score or 0), t.risk or "low"))
        return tools[0]
