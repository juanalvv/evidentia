from __future__ import annotations

import os
from typing import Any, Dict


class PromptLoader:
    """Utility to load and populate prompt templates from markdown files."""

    def __init__(self, template_dir: str | None = None) -> None:
        if template_dir is None:
            # Default to the directory where this file resides
            template_dir = os.path.dirname(__file__)
        self.template_dir = template_dir

    def load(self, name: str, **kwargs: Any) -> str:
        """Load a template by name and populate it with provided variables."""
        if not name.endswith(".md"):
            name = f"{name}.md"
        
        path = os.path.join(self.template_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt template not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            template = f.read()

        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing variable {e} for prompt template {name}") from e


# Singleton instance for easy access
prompt_loader = PromptLoader()
