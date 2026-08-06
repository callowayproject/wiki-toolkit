"""Test frontmatter module."""

import json
from pathlib import Path

import pytest
from pytest import param

from wiki_toolkit.frontmatter import Post, dump_frontmatter, parse_frontmatter

TEST_DIR = Path(__file__).parent

parameters = [
    param("yaml/chinese.txt", "yaml/chinese.result.json", id="chinese"),
    param("yaml/empty-frontmatter.txt", "yaml/empty-frontmatter.result.json", id="empty-frontmatter"),
    param("yaml/extra-space.txt", "yaml/extra-space.result.json", id="extra-space"),
    param("yaml/hello-markdown.md", "yaml/hello-markdown.result.json", id="hello-markdown"),
    param("yaml/hello-world.txt", "yaml/hello-world.result.json", id="hello-world"),
    param("yaml/network-diagrams.md", "yaml/network-diagrams.result.json", id="network-diagrams"),
    param("yaml/no-frontmatter.txt", "yaml/no-frontmatter.result.json", id="no-frontmatter"),
    param("yaml/unpretty.md", "yaml/unpretty.result.json", id="unpretty"),
]


@pytest.mark.parametrize("filename, result_filename", parameters)
def test_parses_files_correctly(filename: str, result_filename: str) -> None:
    """Test that frontmatter is parsed correctly."""
    # Arrange
    original = TEST_DIR / filename
    result = TEST_DIR / result_filename
    results = json.loads(result.read_text())

    # Act
    metadata, content = parse_frontmatter(original.read_text())
    metadata["content"] = content

    # Assert
    assert metadata == results


@pytest.mark.parametrize("filename, result_filename", parameters)
def test_dumps_files_correctly(filename: str, result_filename: str) -> None:
    """Test that frontmatter is dumped correctly."""
    # Arrange
    original = TEST_DIR / filename
    result = TEST_DIR / result_filename
    results = json.loads(result.read_text())

    # Act
    metadata, content = parse_frontmatter(original.read_text())
    dumped_result = dump_frontmatter(metadata, content)
    metadata, content = parse_frontmatter(dumped_result)
    metadata["content"] = content

    # Assert
    assert metadata == results


class TestPost:
    """Tests for the Post class."""

    def test_can_get_content(self) -> None:
        """Test that the content can be retrieved from a Post object."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Assert
        assert post.content == "test_content"

    def test_getattr_returns_value(self) -> None:
        """The __getattr__ method should return the value of the attribute if it exists."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Assert
        assert post["test"] == "test"

    def test_getattr_raises_error_on_missing(self) -> None:
        """The __getattr__ method should raise KeyError if the attribute does not exist."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Assert
        with pytest.raises(KeyError):
            post["nonexistent"]

    def test_contains(self) -> None:
        """The __contains__ method should return True/False correctly."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Assert
        assert "test" in post
        assert "nonexistent" not in post

    def test_delitem_deletes_content(self) -> None:
        """The __delitem__ deletes content from the metadata."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Act
        del post["test"]

        # Assert
        with pytest.raises(KeyError):
            post["test"]

    def test_delitem_raises_error_when_missing(self) -> None:
        """The __delitem__ method raises KeyError when the attribute is missing."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Assert
        with pytest.raises(KeyError):
            post["nonexistent"]

    def test_bytes_encodes_content(self) -> None:
        """The __bytes__ method encodes the content."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Act
        content_bytes = bytes(post)

        # Assert
        assert content_bytes == b"test_content"

    def test_str_returns_content(self) -> None:
        """The __str__ method returns the content."""
        # Arrange
        post = Post({"test": "test"}, "test_content")

        # Act
        content_str = str(post)

        # Assert
        assert content_str == "test_content"
