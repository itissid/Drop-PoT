# MIT License

# Copyright (c) 2023 Anton Osika
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from dataclasses import dataclass
from pathlib import Path
from typing import Union


# This class represents a simple database that stores its data as files in a directory.
class DB:
    """A simple key-value store, where keys are filenames and values are file contents."""

    def __init__(self, path: Union[Path, str]):
        self.path = Path(path).absolute()

        self.path.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, key: Union[str, Path]):
        full_path = self.path / key

        if not full_path.is_file():
            raise KeyError(key)
        with full_path.open("r", encoding="utf-8") as f:
            return f.read()

    def __setitem__(self, key: Union[str, Path], val):
        full_path = self.path / key
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(val, str):
            full_path.write_text(val, encoding="utf-8")
        else:
            # If val is neither a string nor bytes, raise an error.
            raise TypeError("val must be either a str or bytes")


# dataclass for all dbs:
@dataclass
class DBs:
    logs: DB  # Write logs containing transcripts with GPT
    # given a name knows how to load/store documents for scraping.
    ingestion_documents: DB
    prompts: DB  # Knows how to read in prompts that are configured.
