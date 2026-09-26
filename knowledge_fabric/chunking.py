"""Configurable document chunking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChunkConfig:
    strategy: str = "paragraph"  # fixed|paragraph|heading
    max_chars: int = 800
    overlap: int = 100


@dataclass
class ChunkSpec:
    ordinal: int
    content: str
    heading: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    token_estimate: int = 0


def deterministic_chunk_id(document_id: str, ordinal: int, version: int = 1) -> str:
    raw = f"{document_id}:{ordinal}:{version}"
    return "CHK-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def chunk_text(text: str, config: Optional[ChunkConfig] = None) -> List[ChunkSpec]:
    cfg = config or ChunkConfig()
    text = (text or "").strip()
    if not text:
        return []
    if cfg.strategy == "fixed":
        return _fixed(text, cfg)
    if cfg.strategy == "heading":
        return _heading(text, cfg)
    return _paragraph(text, cfg)


def _fixed(text: str, cfg: ChunkConfig) -> List[ChunkSpec]:
    out: List[ChunkSpec] = []
    i = 0
    ordinal = 0
    n = len(text)
    while i < n:
        end = min(i + cfg.max_chars, n)
        piece = text[i:end]
        out.append(ChunkSpec(ordinal=ordinal, content=piece, token_estimate=max(1, len(piece) // 4)))
        ordinal += 1
        if end >= n:
            break
        i = max(end - cfg.overlap, i + 1)
    return out


def _paragraph(text: str, cfg: ChunkConfig) -> List[ChunkSpec]:
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paras:
        return _fixed(text, cfg)
    out: List[ChunkSpec] = []
    buf = ""
    ordinal = 0
    for p in paras:
        if not buf:
            buf = p
        elif len(buf) + 2 + len(p) <= cfg.max_chars:
            buf = buf + "\n\n" + p
        else:
            out.append(ChunkSpec(ordinal=ordinal, content=buf, token_estimate=max(1, len(buf) // 4)))
            ordinal += 1
            # overlap: keep tail of previous
            if cfg.overlap > 0 and len(buf) > cfg.overlap:
                buf = buf[-cfg.overlap :] + "\n\n" + p
            else:
                buf = p
    if buf:
        out.append(ChunkSpec(ordinal=ordinal, content=buf, token_estimate=max(1, len(buf) // 4)))
    return out


def _heading(text: str, cfg: ChunkConfig) -> List[ChunkSpec]:
    lines = text.replace("\r\n", "\n").split("\n")
    sections: List[tuple] = []
    current_heading = None
    buf: List[str] = []
    for line in lines:
        if line.startswith("#"):
            if buf:
                sections.append((current_heading, "\n".join(buf).strip()))
            current_heading = line.lstrip("#").strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        sections.append((current_heading, "\n".join(buf).strip()))
    out: List[ChunkSpec] = []
    ordinal = 0
    for heading, body in sections:
        if not body:
            continue
        for spec in _paragraph(body, cfg):
            out.append(
                ChunkSpec(
                    ordinal=ordinal,
                    content=spec.content,
                    heading=heading,
                    section=heading,
                    token_estimate=spec.token_estimate,
                )
            )
            ordinal += 1
    return out or _paragraph(text, cfg)
