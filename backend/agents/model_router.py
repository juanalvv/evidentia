from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    name: str
    temperature: float = 0.2
    max_tokens: int = 2048


class ModelRouter:
    """Manual model selection for Nemotron Super vs Nano."""

    def __init__(self, super_model: str, nano_model: str) -> None:
        self._super = super_model
        self._nano = nano_model

    def for_reasoning(self) -> ModelRoute:
        return ModelRoute(name=self._super, temperature=0.2, max_tokens=4096)

    def for_scoring(self) -> ModelRoute:
        return ModelRoute(name=self._nano, temperature=0.1, max_tokens=1024)

    def for_dispatch(self) -> ModelRoute:
        return ModelRoute(name=self._nano, temperature=0.0, max_tokens=512)
