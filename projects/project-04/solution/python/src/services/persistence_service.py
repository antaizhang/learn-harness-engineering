"""File-backed persistence. Port of ``src/services/persistence-service.ts``.

All application data is stored locally as JSON/text files under a data
directory -- no database, exactly like the original Electron app.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, List, Optional


class PersistenceService:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.documents_dir = os.path.join(data_dir, "documents")
        self.index_dir = os.path.join(data_dir, "index")
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.documents_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)

    def read_json(self, relative_path: str) -> Optional[Any]:
        """Read a JSON file, returning None if it doesn't exist."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def write_json(self, relative_path: str, data: Any) -> None:
        """Write a JSON file (creating parent directories as needed)."""
        full_path = os.path.join(self.data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def read_text(self, relative_path: str) -> Optional[str]:
        """Read a text file, returning None if it doesn't exist."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_text(self, relative_path: str, content: str) -> None:
        """Write a text file (creating parent directories as needed)."""
        full_path = os.path.join(self.data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def copy_file_to_documents(self, source_path: str, filename: str) -> str:
        """Copy a file into the documents directory."""
        dest_path = os.path.join(self.documents_dir, filename)
        os.makedirs(self.documents_dir, exist_ok=True)
        shutil.copyfile(source_path, dest_path)
        return dest_path

    def delete_from_documents(self, filename: str) -> None:
        """Delete a file from the documents directory."""
        file_path = os.path.join(self.documents_dir, filename)
        if os.path.exists(file_path):
            os.unlink(file_path)

    def list_files(self, relative_path: str) -> List[str]:
        """List all files in a directory."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            return []
        return os.listdir(full_path)

    def exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.data_dir, relative_path))

    def get_data_dir(self) -> str:
        return self.data_dir

    def get_documents_dir(self) -> str:
        return self.documents_dir

    def get_index_dir(self) -> str:
        return self.index_dir
