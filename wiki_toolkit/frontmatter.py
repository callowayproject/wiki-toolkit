"""Parse frontmatter from content string."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable


def force_unicode(text: str | bytes, encoding: str = "utf-8") -> str:
    """Return Unicode text no matter what."""
    if isinstance(text, bytes):
        text_str: str = text.decode(encoding)
    else:
        text_str = str(text)

    return text_str.replace("\r\n", "\n")


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse frontmatter from content string.

    Args:
        content: The file content as a string

    Returns:
        Tuple of (frontmatter_dict, remaining_content)

    Raises:
        ValueError: If the frontmatter is invalid YAML
    """
    # Look for YAML frontmatter delimited by ---
    pattern = r"^---\s*\n(.*?)\n?---\s*\n?(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        # No frontmatter found
        return {}, content

    frontmatter_content = match.group(1)
    remaining_content = match.group(2) or ""

    frontmatter = yaml.safe_load(frontmatter_content)
    return frontmatter or {}, remaining_content.strip()


def dump_frontmatter(metadata: dict[str, Any] | None, content: str) -> str:
    """
    Dump frontmatter metadata and content into a string.

    Args:
        metadata: The frontmatter metadata as a dictionary.
        content: The content string.

    Returns:
        The combined frontmatter and content string. If metadata is None, only the content is returned.
    """
    if not metadata:
        return content

    metadata_str = yaml.safe_dump(metadata, default_flow_style=False, allow_unicode=True).strip()
    metadata_str = force_unicode(metadata_str)

    return f"---\n{metadata_str}\n---\n\n{content}".strip()


class Post:
    """
    A post contains content and metadata from frontmatter. This is what gets returned by `parse_frontmatter`.

    For convenience, metadata values are available as proxied item lookups.
    """

    def __init__(self, metadata: dict[str, Any], content: str) -> None:
        self._content = str(content)
        self._metadata = metadata

    @classmethod
    def loads(cls, content: str) -> Post:
        """Create a Post from a string of Markdown content."""
        return cls(*parse_frontmatter(content))

    def dumps(self) -> str:
        """Dump the post to a string of Markdown content."""
        return dump_frontmatter(self._metadata, self._content)

    @property
    def content(self) -> str:
        """The content of the post."""
        return self._content

    @property
    def metadata(self) -> dict[str, Any]:
        """The metadata of the post."""
        return self._metadata

    def __getitem__(self, name: str) -> Any:
        """Get metadata key."""
        return self._metadata[name]

    def __contains__(self, key: Any) -> bool:
        """Check metadata contains the key."""
        return key in self._metadata

    def __setitem__(self, name: str, value: Any) -> None:
        """Set a metadata key."""
        self._metadata[name] = value

    def __delitem__(self, name: str) -> None:
        """Delete a metadata key."""
        del self._metadata[name]

    def __bytes__(self) -> bytes:
        return self._content.encode("utf-8")

    def __str__(self) -> str:
        return self._content

    def get(self, key: str, default: Any = None) -> Any:
        """Get a key, fallback to default."""
        return self._metadata.get(key, default)

    def keys(self) -> Iterable[str]:
        """Return metadata keys."""
        return self._metadata.keys()

    def values(self) -> Iterable[Any]:
        """Return metadata values."""
        return self._metadata.values()

    def to_dict(self) -> dict[str, Any]:
        """Post as a dict, for serializing."""
        d = self._metadata.copy()
        d["content"] = self._content
        return d
