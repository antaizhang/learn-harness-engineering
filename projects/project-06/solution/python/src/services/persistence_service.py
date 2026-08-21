"""File-backed persistence. Port of ``src/services/persistence-service.ts``.

All application data is stored locally as JSON/text files under a data
directory -- no database, exactly like the original Electron app.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, List, Optional

from .logger import logger

SERVICE = "persistence"


class PersistenceService:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.documents_dir = os.path.join(data_dir, "documents")
        self.index_dir = os.path.join(data_dir, "index")
        self._ensure_directories()
        logger.info(SERVICE, "PersistenceService initialized", {"dataDir": data_dir})

    def _ensure_directories(self) -> None:
        for directory in (self.data_dir, self.documents_dir, self.index_dir):
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.debug(SERVICE, "Created directory", {"dir": directory})

    def read_json(self, relative_path: str) -> Optional[Any]:
        """Read a JSON file, returning None if it doesn't exist."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            logger.debug(SERVICE, "File not found (returning null)", {"path": relative_path})
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.debug(SERVICE, "Read JSON file", {"path": relative_path})
            return data
        except (ValueError, OSError) as err:
            logger.error(SERVICE, "Failed to parse JSON file", {"path": relative_path, "error": str(err)})
            return None

    def write_json(self, relative_path: str, data: Any) -> None:
        """Write a JSON file (creating parent directories as needed)."""
        full_path = os.path.join(self.data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        serialized = json.dumps(data, indent=2)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(serialized)
        logger.debug(
            SERVICE,
            "Wrote JSON file",
            {"path": relative_path, "sizeBytes": len(serialized.encode("utf-8"))},
        )

    def read_text(self, relative_path: str) -> Optional[str]:
        """Read a text file, returning None if it doesn't exist."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            logger.debug(SERVICE, "Text file not found", {"path": relative_path})
            return None
        with open(full_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        logger.debug(SERVICE, "Read text file", {"path": relative_path, "length": len(content)})
        return content

    def write_text(self, relative_path: str, content: str) -> None:
        """Write a text file (creating parent directories as needed)."""
        full_path = os.path.join(self.data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.debug(SERVICE, "Wrote text file", {"path": relative_path, "length": len(content)})

    def copy_file_to_documents(self, source_path: str, filename: str) -> str:
        """Copy a file into the documents directory."""
        dest_path = os.path.join(self.documents_dir, filename)
        os.makedirs(self.documents_dir, exist_ok=True)
        shutil.copyfile(source_path, dest_path)
        logger.info(SERVICE, "Copied file to documents", {"source": source_path, "filename": filename})
        return dest_path

    def delete_from_documents(self, filename: str) -> None:
        """Delete a file from the documents directory."""
        file_path = os.path.join(self.documents_dir, filename)
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(SERVICE, "Deleted document file", {"filename": filename})

    def list_files(self, relative_path: str) -> List[str]:
        """List all files in a directory."""
        full_path = os.path.join(self.data_dir, relative_path)
        if not os.path.exists(full_path):
            return []
        return os.listdir(full_path)

    def exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.data_dir, relative_path))

    def reset_all(self) -> None:
        """Delete all stored data and recreate directories."""
        logger.warn(SERVICE, "Resetting all data", {"dataDir": self.data_dir})
        shutil.rmtree(self.data_dir, ignore_errors=True)
        self._ensure_directories()
        logger.info(SERVICE, "Data reset complete")

    def get_data_dir(self) -> str:
        return self.data_dir

    def get_documents_dir(self) -> str:
        return self.documents_dir

    def get_index_dir(self) -> str:
        return self.index_dir
