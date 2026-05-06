import json
from typing import Any

import structlog

from server._logging import configure_logging, get_logger


def test_get_logger_returns_structlog_logger() -> None:
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    assert isinstance(log, structlog.stdlib.BoundLogger) or hasattr(log, "info")


def test_configure_logging_emits_json(capsys: Any) -> None:
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    log.info("hello", k="v")
    captured = capsys.readouterr()
    line: str = captured.err.strip().splitlines()[-1]
    parsed: dict[str, Any] = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["k"] == "v"
    assert parsed["level"] == "info"


def test_configure_logging_console_mode_does_not_emit_json(capsys: Any) -> None:
    configure_logging(level="INFO", json=False)
    log = get_logger("test")
    log.info("hello-console")
    captured = capsys.readouterr()
    line: str = captured.err.strip().splitlines()[-1]
    assert "hello-console" in line
    # console renderer is not JSON
    try:
        json.loads(line)
        raise AssertionError("expected non-JSON output in console mode")
    except json.JSONDecodeError:
        pass


def test_configure_logging_idempotent() -> None:
    configure_logging(level="INFO", json=True)
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    log.info("idempotent-ok")
