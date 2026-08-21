"""Structured logging module for the Knowledge Base application.

Provides log levels, timestamps, and structured JSON output for all services.
Replaces raw ``print`` calls with consistent, machine-parseable log entries.
Port of ``src/services/logger.ts``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


_LEVEL_ORDER = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Logger:
    def __init__(self, min_level: LogLevel = LogLevel.DEBUG) -> None:
        self.min_level = min_level

    def _should_log(self, level: LogLevel) -> bool:
        return _LEVEL_ORDER.index(level) >= _LEVEL_ORDER.index(self.min_level)

    def _emit(self, entry: Dict[str, Any]) -> None:
        output = json.dumps(entry)
        stream = sys.stderr if entry["level"] in (LogLevel.ERROR.value, LogLevel.WARN.value) else sys.stdout
        print(output, file=stream)

    def _log(
        self,
        level: LogLevel,
        service: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._should_log(level):
            return

        entry: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "level": level.value,
            "service": service,
            "message": message,
        }
        if data:
            entry["data"] = data

        self._emit(entry)

    def debug(self, service: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(LogLevel.DEBUG, service, message, data)

    def info(self, service: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(LogLevel.INFO, service, message, data)

    def warn(self, service: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(LogLevel.WARN, service, message, data)

    def error(self, service: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(LogLevel.ERROR, service, message, data)

    def for_service(self, service_name: str) -> "ServiceLogger":
        """Create a child logger scoped to a specific service."""
        return ServiceLogger(self, service_name)


class ServiceLogger:
    def __init__(self, logger: Logger, service_name: str) -> None:
        self.logger = logger
        self.service_name = service_name

    def debug(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.debug(self.service_name, message, data)

    def info(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.info(self.service_name, message, data)

    def warn(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.warn(self.service_name, message, data)

    def error(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.error(self.service_name, message, data)


def _resolve_level() -> LogLevel:
    raw = os.environ.get("LOG_LEVEL")
    if raw:
        try:
            return LogLevel(raw.upper())
        except ValueError:
            pass
    return LogLevel.DEBUG


# Singleton logger instance for the application.
logger = Logger(_resolve_level())
