from unittest.mock import patch
import pytest
import typer
from utils.cli_utils import validate_url_file_suggestions

def test_empty_data():
    with pytest.raises(ValueError, match="Bad data: missing URL or file names."):
        validate_url_file_suggestions([{}])

def test_missing_url():
    with pytest.raises(ValueError, match="Bad data: missing URL or file names."):
        validate_url_file_suggestions([{"file_names": {"a": "file1", "b": "file2", "c": "file3"}}])

def test_missing_file_names():
    with pytest.raises(ValueError, match="Bad data: missing URL or file names."):
        validate_url_file_suggestions([{"url": "http://example.com"}])
