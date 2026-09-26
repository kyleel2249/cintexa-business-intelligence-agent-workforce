"""Computer-use abstraction — interface only; no unrestricted host control."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ComputerUseProvider(ABC):
    @abstractmethod
    def move(self, x: int, y: int) -> Dict[str, Any]: ...

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]: ...

    @abstractmethod
    def type_text(self, text: str) -> Dict[str, Any]: ...

    @abstractmethod
    def scroll(self, dx: int, dy: int) -> Dict[str, Any]: ...

    @abstractmethod
    def screenshot(self) -> Dict[str, Any]: ...

    @abstractmethod
    def inspect(self) -> Dict[str, Any]: ...


class NullComputerProvider(ComputerUseProvider):
    """Safe default — records intent without controlling the host desktop."""

    def move(self, x: int, y: int) -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "move", "x": x, "y": y}

    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "click", "x": x, "y": y, "button": button}

    def type_text(self, text: str) -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "type", "length": len(text or "")}

    def scroll(self, dx: int, dy: int) -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "scroll", "dx": dx, "dy": dy}

    def screenshot(self) -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "screenshot"}

    def inspect(self) -> Dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "action": "inspect"}
