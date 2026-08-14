"""Logging infrastructure: global SharedLogger, ModuleLogger, CaptureStream for
task-scoped output buffering, and CustomFormatter for trimmed log lines.
"""

from __future__ import annotations

import io
import logging
import sys
import threading
from collections import defaultdict
from typing import BinaryIO, TextIO, Union, Optional

_logger_creation_lock = threading.Lock()


class SharedLogger:
    """Singleton that all module loggers write to. It forwards records to the
    standard logging framework (root logger) and mirrors them into a bounded
    in-memory buffer (LogQueueHandler) so recent output can be retrieved
    programmatically (e.g., for status reporting in UIs)."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if SharedLogger._instance is not None:
            raise RuntimeError("SharedLogger is a singleton - use SharedLogger.get()")
        self._root = logging.getLogger()
        self._handler = _LogQueueHandler(1500)
        self._handler.setFormatter(CustomFormatter())
        self._root.addHandler(self._handler)
        self._root.setLevel(logging.DEBUG)
        self._enabled = True
        self._level = logging.DEBUG
        self._frontend_level = logging.DEBUG
        self._frontend_enabled = True
        self._sinks = set()

    @classmethod
    def get(cls) -> "SharedLogger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SharedLogger()
        return cls._instance

    def attach(self, sink: "LogSink") -> None:
        self._sinks.add(sink)

    def detach(self, sink: "LogSink") -> None:
        self._sinks.discard(sink)

    def handle(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return
        if record.levelno < self._level:
            return
        if record.name.startswith("comfyui_integration.logging_frontend"):
            frontend_record = self._make_frontend_record(record)
            self._root.handle(frontend_record)
        else:
            self._root.handle(record)

        for sink in list(self._sinks):
            try:
                sink.write(record)
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def level(self) -> int:
        return self._level

    def set_level(self, value: int) -> None:
        self._level = value

    def set_frontend_enabled(self, value: bool) -> None:
        self._frontend_enabled = value

    def set_frontend_level(self, value: int) -> None:
        self._frontend_level = value

    def _make_frontend_record(self, record: logging.LogRecord) -> logging.LogRecord:
        import copy

        new_record = copy.copy(record)
        new_record.name = "comfyui_integration.frontend"
        return new_record

    def get_logs(self, last_n: int = 400) -> list[str]:
        return self._handler.get_logs(last_n)

    def clear_logs(self) -> None:
        self._handler.clear_logs()

    def _handler_attached(self, key: str) -> bool:
        target = self._resolve_target(key)
        return target in self._handler.child_targets()

    def _resolve_target(self, key: str) -> str:
        if key in ("root", "comfyui_integration", "comfyui_integration.frontend"):
            return key
        return key

    def _attach_dynamic_handler(self, key: str, capture: "CaptureStream") -> None:
        self._handler.attach_child(GlobalOutputHandler(key, capture))

    def _detach_dynamic_handler(self, key: str, capture: "CaptureStream") -> None:
        self._handler.detach_child(GlobalOutputHandler(key, capture))

    def _register_task_capture(self, task_name: str) -> None:
        self._handler.register_task(task_name)

    def _unregister_task_capture(self, task_name: str) -> None:
        self._handler.unregister_task(task_name)

    def get_task_logs(self, task_name: str, last_n: int = 400) -> list[str]:
        return self._handler.get_task_logs(task_name, last_n)

    def clear_task_logs(self, task_name: str) -> None:
        self._handler.clear_task_logs(task_name)

    def get_task_capture_buffer(self, task_name: str) -> Optional["CaptureStream"]:
        return self._handler.get_task_capture_buffer(task_name)


class _LogQueueHandler(logging.Handler):
    """Bounded deque of formatted log lines plus per-domain mirrors."""

    def __init__(self, maxlen=1500):
        super().__init__()
        self.maxlen = maxlen
        self._queue = deque(maxlen=maxlen)
        self._child_targets: set[str] = set()
        self._task_captures: dict[str, "CaptureStream"] = {}
        self._lock = threading.Lock()

    def child_targets(self) -> set[str]:
        with self._lock:
            return set(self._child_targets)

    def attach_child(self, handler: "GlobalOutputHandler") -> None:
        with self._lock:
            self._child_targets.add(handler.target_key)
            self._queue = deque(
                [line for line in self._queue if handler.matches(line)],
                maxlen=self.maxlen,
            )
            self._child_targets.add(handler.target_key)

    def detach_child(self, handler: "GlobalOutputHandler") -> None:
        with self._lock:
            self._child_targets.discard(handler.target_key)

    def register_task(self, task_name: str) -> None:
        with self._lock:
            if task_name not in self._task_captures:
                capture = CaptureStream(task_name)
                self._task_captures[task_name] = capture
                self._queue = deque([], maxlen=self.maxlen)

    def unregister_task(self, task_name: str) -> None:
        with self._lock:
            self._task_captures.pop(task_name, None)

    def get_task_capture_buffer(self, task_name: str) -> Optional["CaptureStream"]:
        with self._lock:
            return self._task_captures.get(task_name)

    def set_task_capture_buffer(self, key: str, capture: "CaptureStream") -> None:
        with self._lock:
            self._task_captures[key] = capture

    def get_task_logs(self, task_name: str, last_n: int) -> list[str]:
        with self._lock:
            capture = self._task_captures.get(task_name)
            if capture is None:
                return []
            return capture.get_lines(last_n)

    def clear_task_logs(self, task_name: str) -> None:
        with self._lock:
            capture = self._task_captures.get(task_name)
            if capture is not None:
                capture.clear()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            line = record.getMessage()
        with self._lock:
            if self._child_targets:
                self._queue = deque(
                    [item for item in self._queue if not self._matches_any(item, record)],
                    maxlen=self.maxlen,
                )
            self._queue.append((line, record))

    def _matches_any(self, line: str, record: logging.LogRecord) -> bool:
        return False

    def get_logs(self, last_n: int) -> list[str]:
        with self._lock:
            return [line for line, _ in self._queue][-last_n:]

    def clear_logs(self) -> None:
        with self._lock:
            self._queue.clear()


class GlobalOutputHandler:
    """Bridge that forwards log records to a task-scoped CaptureStream whose
    prefix matches the handler's target key."""

    def __init__(self, target_key: str, capture: "CaptureStream"):
        self.target_key = target_key
        self.capture = capture

    def matches(self, line: str) -> bool:
        return self.target_key in line

    def emit(self, record: logging.LogRecord) -> None:
        self.capture.write(record)


class CaptureStream(io.TextIOWrapper):
    """A synchronous, thread-safe, text stream that accumulates all lines
    written to it (via write/print) plus any logging records forwarded to it,
    keeping up to ``maxlen`` recent lines."""

    def __init__(self, name: str = "capture", maxlen: int = 800):
        self._name = name
        self._maxlen = maxlen
        self._lines_deque = deque(maxlen=maxlen)
        self._buffer = io.StringIO()
        self._lock = threading.RLock()
        super().__init__(io.BytesIO(), encoding="utf-8", line_buffering=True)
        self._stdout_sink = None

    def attach_stdout(self, sink: TextIO) -> None:
        with self._lock:
            self._stdout_sink = sink

    def flush(self) -> None:
        with self._lock:
            content = self._buffer.getvalue()
            if content:
                self._lines_deque.extend(content.splitlines())
                self._buffer = io.StringIO()
            if self._stdout_sink is not None:
                self._stdout_sink.flush()

    def write(self, s: str) -> int:
        with self._lock:
            if self._stdout_sink is not None:
                try:
                    self._stdout_sink.write(s)
                except Exception:
                    pass
            self._buffer.write(s)
            if "\n" in s:
                content = self._buffer.getvalue()
                parts = content.splitlines()
                for part in parts:
                    self._lines_deque.append(part)
                self._buffer = io.StringIO()
            return len(s)

    def get_lines(self, last_n: int | None = None) -> list[str]:
        with self._lock:
            lines = list(self._lines_deque)
            return lines[-last_n:] if last_n else lines

    def clear(self) -> None:
        with self._lock:
            self._lines_deque.clear()
            self._buffer = io.StringIO()

    def name(self) -> str:
        return self._name


class ModuleLogger:
    def __init__(self, name: str, level=logging.DEBUG):
        self._name = name
        self._logger = logging.getLogger(name)
        self._logger.propagate = False
        self._handler = _ForwardingHandler(SharedLogger.get())
        self._handler.setFormatter(CustomFormatter())

        if self._logger.handlers:
            older_handlers = [h for h in self._logger.handlers if getattr(h, "is_attachment", False)]
            for h in older_handlers:
                self._logger.removeHandler(h)
        self._logger.addHandler(self._handler)
        self._logger.setLevel(level)

    @property
    def name(self) -> str:
        return self._name

    def debug(self, message: str, *args, **kwargs) -> None:
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._logger.error(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self._logger.exception(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        self._logger.critical(message, *args, **kwargs)

    def log(self, level: int, message: str, *args, **kwargs) -> None:
        self._logger.log(level, message, *args, **kwargs)

    def get_underlying_logger(self) -> logging.Logger:
        return self._logger

    def set_level(self, level) -> None:
        self._logger.setLevel(level)

    def get_level(self) -> int:
        return self._logger.level


class _ForwardingHandler(logging.Handler):
    is_attachment = True

    def __init__(self, shared: SharedLogger):
        super().__init__()
        self._shared = shared

    def emit(self, record: logging.LogRecord) -> None:
        self._shared.handle(record)


class _CaptureHandler(logging.Handler):
    def __init__(self, stream: CaptureStream):
        super().__init__()
        self._stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._stream.write(self.format(record))
        except Exception:
            pass


class CustomFormatter(logging.Formatter):
    """Formats records into short, single-line messages:
    `LEVEL <logger_name> message`. Non-message fields are not shown."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        level = record.levelname.upper()
        if record.name and record.name != "root":
            return f"{level} <{record.name}> {message}"
        return f"{level} {message}"


class LogSink:
    def attach(self, shared: SharedLogger) -> None:
        pass

    def write(self, record: logging.LogRecord) -> None:
        pass

    def flush(self) -> None:
        pass


class ModuleLogSink(LogSink):
    def __init__(self, logger: ModuleLogger):
        self._logger = logger

    def write(self, record: logging.LogRecord) -> None:
        self._logger.log(record.levelno, record.getMessage())


class FileLogSink(LogSink):
    def __init__(self, path: str):
        self._path = path
        self._file: BinaryIO | None = None

    def attach(self, shared: SharedLogger) -> None:
        self._file = open(self._path, "ab")

    def write(self, record: logging.LogRecord) -> None:
        if self._file is not None:
            line = (
                f"{record.asctime} {record.levelname} {record.name}: {record.getMessage()}\n"
            )
            self._file.write(line.encode())

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()


def get_logger(name: str) -> ModuleLogger:
    key_parts = name.split(".")
    if len(key_parts) >= 3 and (
        key_parts[-3:] == ["comfyui", "integrations", "frontend"]
        or key_parts[-3:] == ["comfyui", "integration", "frontend"]
    ):
        name = "comfyui_integration.frontend"
    elif name.startswith("comfyui_integration"):
        name = "comfyui_integration"

    if name == "" or name is None:
        name = "root"

    with _logger_creation_lock:
        existing = logging.getLogger(name)
        if name == "root":
            shared = SharedLogger.get()
            result = ModuleLogger(name)
            if not shared._handler_attached(name):
                shared.attach(_RootLogSink(result))
            return result

        for handler in existing.handlers:
            if isinstance(handler, _ForwardingHandler):
                return ModuleLogger(name)
        return ModuleLogger(name)


class _RootLogSink(LogSink):
    def __init__(self, logger: ModuleLogger):
        self._logger = logger

    def write(self, record: logging.LogRecord) -> None:
        self._logger.log(record.levelno, record.getMessage())


def _try_get_shared_logger() -> Optional[SharedLogger]:
    try:
        return SharedLogger.get()
    except Exception:
        return None


def configure_package_logging(level: int = logging.DEBUG) -> None:
    shared = SharedLogger.get()
    shared.set_enabled(True)
    shared.set_level(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)


def set_level(level: int) -> None:
    SharedLogger.get().set_level(level)


def set_enabled(level: int = logging.DEBUG) -> None:
    SharedLogger.get().set_enabled(True)
    SharedLogger.get().set_level(level)


def enable_console(level: int = logging.DEBUG) -> None:
    SharedLogger.get().set_level(level)


def capture_logs(
    logger: logging.Logger | None = None,
    stream: CaptureStream | None = None,
    level: int = logging.DEBUG,
) -> CaptureStream:
    if stream is None:
        stream = CaptureStream()
    handler = _CaptureHandler(stream)
    handler.setLevel(level)
    if logger is None or logger is logging.root:
        logging.getLogger().addHandler(handler)
        stream.register_cleanup(lambda: logging.getLogger().removeHandler(handler))
    else:
        logger.addHandler(handler)
        stream.register_cleanup(lambda: logger.removeHandler(handler))
    return stream