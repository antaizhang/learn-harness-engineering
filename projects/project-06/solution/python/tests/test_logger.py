"""Tests for the structured logger (port of the logging module)."""

import json

from src.services.logger import Logger, LogLevel


def test_logger_emits_structured_json(capsys):
    log = Logger(LogLevel.DEBUG).for_service("TestSvc")
    log.info("hello", {"a": 1})
    out = capsys.readouterr().out.strip()
    entry = json.loads(out)
    assert entry["level"] == "INFO"
    assert entry["service"] == "TestSvc"
    assert entry["message"] == "hello"
    assert entry["data"] == {"a": 1}
    assert "timestamp" in entry


def test_logger_respects_min_level(capsys):
    log = Logger(LogLevel.WARN)
    log.info("Svc", "should be filtered")
    log.warn("Svc", "should appear")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "should be filtered" not in combined
    assert "should appear" in combined


def test_logger_omits_empty_data(capsys):
    Logger(LogLevel.DEBUG).info("Svc", "no data")
    entry = json.loads(capsys.readouterr().out.strip())
    assert "data" not in entry


def test_error_goes_to_stderr(capsys):
    Logger(LogLevel.DEBUG).error("Svc", "boom")
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "boom" not in captured.out
