"""
Base prompt builder class.

Provides common functionality for building prompts.
"""

from typing import List


class BasePromptBuilder:
    """
    Base class for prompt builders.

    Provides utilities for constructing structured prompts.
    """

    @staticmethod
    def join_parts(parts: List[str]) -> str:
        """
        Join prompt parts with newlines.

        Args:
            parts: List of prompt sections

        Returns:
            Joined prompt string
        """
        return "\n".join(parts)

    @staticmethod
    def format_section(title: str, content: str = None) -> List[str]:
        """
        Format a section with title and optional content.

        Args:
            title: Section title
            content: Optional section content

        Returns:
            List of formatted lines
        """
        lines = [f"## {title}"]
        if content:
            lines.extend(["", content, ""])
        else:
            lines.append("")
        return lines

    @staticmethod
    def format_subsection(title: str, content: str = None) -> List[str]:
        """
        Format a subsection with title and optional content.

        Args:
            title: Subsection title
            content: Optional subsection content

        Returns:
            List of formatted lines
        """
        lines = [f"### {title}"]
        if content:
            lines.extend(["", content, ""])
        else:
            lines.append("")
        return lines

    @staticmethod
    def format_list(items: List[str], prefix: str = "-") -> str:
        """
        Format a list of items.

        Args:
            items: List of items
            prefix: Bullet point prefix

        Returns:
            Formatted list string
        """
        return "\n".join([f"{prefix} {item}" for item in items])
