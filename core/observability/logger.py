"""Shared backend logging utilities."""

from __future__ import annotations

import sys
import io
import logging
import time
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from collections.abc import Iterator
from typing import ClassVar, Literal, overload

# ── Global tqdm tuning ────────────────────────────────────────────────
import tqdm as _tqdm_module

_tqdm_module.tqdm.mininterval = 1.0

import os

# Create the package-level logger immediately so that all child loggers
# created during module import have the correct parent chain instead of
# falling back to root.  Set to DEBUG so early import-time log calls pass
# isEnabledFor(); configure_package_logging() will pin the final level later.
logging.getLogger("comfyui_image_scorer").setLevel(logging.DEBUG)


LogLevelName = Literal["debug", "info", "warning", "error", "critical"]


def _custom_find_caller(
    _self: object,
    stack_info: bool = False,
    _stacklevel: int = 1,
) -> tuple[str, int, str, str | None]:
    f = sys._getframe(1)  # pyright: ignore[reportPrivateUsage]
    while f is not None and getattr(f, "f_code", None):
        co = f.f_code
        filename = os.path.normcase(co.co_filename)
        if "logger.py" in filename or filename == logging._srcfile:
            f = f.f_back
        else:
            break
    if f is None:
        return "(unknown file)", 0, "(unknown function)", None

    co = f.f_code
    sinfo = None
    if stack_info:
        sio = io.StringIO()
        sio.write("Stack (most recent call last):\n")
        traceback.print_stack(f, file=sio)
        sinfo = sio.getvalue()
        if sinfo[-1] == "\n":
            sinfo = sinfo[:-1]
        sio.close()
    return co.co_filename, f.f_lineno, co.co_name, sinfo


logging.Logger.findCaller = _custom_find_caller


# ── Synchronous log capture (for server command endpoints) ───────────


class _CaptureHandler(logging.Handler):
    """Collects formatted package log records into a line list."""

    def __init__(self, lines: list[str], level: int) -> None:
        super().__init__(level)
        self._lines = lines
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self._lines.append(self.format(record))


@contextmanager
def capture_log_output() -> Iterator[list[str]]:
    """Collect log output (package log records + stdout/stderr writes) during
    an endpoint's synchronous command execution into the yielded line list."""
    lines: list[str] = []
    handler = _CaptureHandler(lines, logging.INFO)
    package_logger = logging.getLogger("comfyui_image_scorer")
    package_logger.addHandler(handler)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            yield lines
    finally:
        package_logger.removeHandler(handler)
        for buf in (stdout_buf, stderr_buf):
            text = buf.getvalue()
            if text:
                lines.extend(line for line in text.splitlines() if line)


class ModuleLogger:
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name

    @property
    def _underlying(self) -> logging.Logger:
        return logging.getLogger(self.module_name)

    @property
    def level(self) -> int:
        return self._underlying.level

    @level.setter
    def level(self, value: int) -> None:
        self._underlying.level = value

    def setLevel(self, level: int) -> None:
        self._underlying.setLevel(level)

    def addHandler(self, hdlr: logging.Handler) -> None:
        self._underlying.addHandler(hdlr)

    def removeHandler(self, hdlr: logging.Handler) -> None:
        self._underlying.removeHandler(hdlr)

    def log(
        self,
        level_name: LogLevelName,
        message: str,
        *args: object,
        start_timer: float | None = None,
    ) -> None:
        if args:
            message = message % args
        SharedLogger.log(
            module_name=self.module_name,
            level_name=level_name,
            message=message,
            start_timer=start_timer,
        )

    def debug(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("debug", message, *args, start_timer=start_timer)

    def info(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("info", message, *args, start_timer=start_timer)

    def warning(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("warning", message, *args, start_timer=start_timer)

    def error(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("error", message, *args, start_timer=start_timer)

    def exception(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("error", message, *args, start_timer=start_timer)

    def critical(
        self, message: str, *args: object, start_timer: float | None = None
    ) -> None:
        self.log("critical", message, *args, start_timer=start_timer)


class _DynamicModuleFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return SharedLogger.should_emit(record.name)


class SharedLogger:
    """Centralized backend logger.

    Filtering (name/level), formatting, and console output live here.
    """

    allowed_exact_names: ClassVar[frozenset[str]] = frozenset()
    allowed_prefixes: ClassVar[tuple[str, ...]] = ()
    _name_filter: ClassVar[_DynamicModuleFilter] = _DynamicModuleFilter()

    @classmethod
    def install_root_filter(cls) -> None:
        root_logger = logging.getLogger()
        if cls._name_filter not in root_logger.filters:
            root_logger.addFilter(cls._name_filter)

    @classmethod
    def set_name_filters(
        cls,
        exact_names: set[str] | frozenset[str] | tuple[str, ...] | list[str],
        prefixes: tuple[str, ...] | list[str],
    ) -> None:
        cls.allowed_exact_names = frozenset(exact_names)
        cls.allowed_prefixes = tuple(prefixes)

    @classmethod
    def clear_name_filters(cls) -> None:
        cls.allowed_exact_names = frozenset()
        cls.allowed_prefixes = ()

    @classmethod
    def should_emit(cls, module_name: str) -> bool:
        if not cls.allowed_exact_names and not cls.allowed_prefixes:
            return True
        if module_name in cls.allowed_exact_names:
            return True
        result = any(module_name.startswith(prefix) for prefix in cls.allowed_prefixes)
        return result

    @classmethod
    def get_logger(cls, module_name: str) -> ModuleLogger:
        cls.install_root_filter()
        result = ModuleLogger(module_name)
        return result

    # ── Formatting ────────────────────────────────────────────────────

    @classmethod
    def format_message(cls, message: str, start_timer: float | None) -> str:
        result = message

        if start_timer is not None:
            result = f"{message} ({time.perf_counter() - start_timer:.4f}s)"
        return result

    # ── The log method ────────────────────────────────────────────────

    @classmethod
    def log(
        cls,
        module_name: str,
        level_name: LogLevelName,
        message: str,
        start_timer: float | None,
    ) -> None:
        cls.install_root_filter()
        if not cls.should_emit(module_name):
            return

        rendered_message = cls.format_message(message, start_timer)
        level = cls._normalize_level(level_name)
        _logger = logging.getLogger(module_name)
        _logger.log(
            level,
            rendered_message,
            extra={"_shared_logger_managed": True},
        )

    @staticmethod
    def _normalize_level(level_name: LogLevelName) -> int:
        level_map: dict[LogLevelName, int] = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        result = level_map[level_name]
        return result


class CustomFormatter(logging.Formatter):
    """Custom formatter to trim level names, module names, function names, and messages."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        trim_level_len: int | None = 3,
        trim_module_len: int | None = 15,
        trim_func_len: int | None = 15,
        trim_msg_len: int | None = None,
    ) -> None:
        super().__init__(fmt, datefmt)
        self.trim_level_len = trim_level_len
        self.trim_module_len = trim_module_len
        self.trim_func_len = trim_func_len
        self.trim_msg_len = trim_msg_len

    def format(self, record: logging.LogRecord) -> str:
        orig_levelname = record.levelname
        orig_name = record.name
        orig_funcName = record.funcName
        orig_msg = record.msg
        orig_args = record.args

        # Trim levelname
        if self.trim_level_len is not None:
            level_map = {
                "DEBUG": "DBG",
                "INFO": "INF",
                "WARNING": "WRN",
                "ERROR": "ERR",
                "CRITICAL": "CRT",
            }
            if self.trim_level_len == 3:
                record.levelname = level_map.get(orig_levelname, orig_levelname[:3])
            else:
                record.levelname = orig_levelname[: self.trim_level_len]

        # Trim module name to keep the last N characters (from the end)
        if self.trim_module_len is not None and orig_name:
            if len(orig_name) > self.trim_module_len:
                if self.trim_module_len > 3:
                    record.name = "..." + orig_name[-(self.trim_module_len - 3) :]
                else:
                    record.name = orig_name[-self.trim_module_len :]

        # Trim function name to keep the last N characters (from the end)
        if self.trim_func_len is not None and orig_funcName:
            if len(orig_funcName) > self.trim_func_len:
                if self.trim_func_len > 3:
                    record.funcName = "..." + orig_funcName[-(self.trim_func_len - 3) :]
                else:
                    record.funcName = orig_funcName[-self.trim_func_len :]

        # Trim message length
        if self.trim_msg_len is not None:
            msg = record.getMessage()
            if len(msg) > self.trim_msg_len:
                if self.trim_msg_len > 3:
                    record.msg = msg[: self.trim_msg_len - 3] + "..."
                else:
                    record.msg = msg[: self.trim_msg_len]
                record.args = ()

        result = super().format(record)
        # Restore original values so other handlers/formatters are unaffected
        record.levelname = orig_levelname
        record.name = orig_name
        record.funcName = orig_funcName
        record.msg = orig_msg
        record.args = orig_args

        return result


@overload
def get_logger(module_name: None = None) -> logging.Logger: ...


@overload
def get_logger(module_name: str) -> ModuleLogger: ...


def get_logger(module_name: str | None = None) -> logging.Logger | ModuleLogger:
    if module_name is None:
        return logging.getLogger()
    result: ModuleLogger = SharedLogger.get_logger(module_name)
    return result


def configure_package_logging(
    level: int = logging.INFO,
    fmt: str | None = None,
    *,
    datefmt: str | None = "%H:%M:%S",
    trim_level_len: int | None = 3,
    trim_module_len: int | None = 15,
    trim_func_len: int | None = 15,
    trim_msg_len: int | None = None,
) -> None:
    if fmt is None:
        fmt = "[%(levelname)s] [%(name)s] [%(funcName)s] %(asctime)s %(message)s"

    logging.basicConfig(
        format=fmt,
        datefmt=datefmt,
    )

    # Apply CustomFormatter to all root handlers to handle the trimming
    formatter = CustomFormatter(
        fmt,
        datefmt=datefmt,
        trim_level_len=trim_level_len,
        trim_module_len=trim_module_len,
        trim_func_len=trim_func_len,
        trim_msg_len=trim_msg_len,
    )
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    logging.getLogger("__main__").setLevel(level)

    pkg_logger = logging.getLogger("comfyui_image_scorer")
    pkg_logger.setLevel(level)
    # Rewire parent links in case any child loggers were created before
    # the package logger existed, then clear level caches.
    logging.root.manager._fixupParents(pkg_logger)
    for _log_name, _log in list(logging.root.manager.loggerDict.items()):
        if isinstance(_log, logging.Logger) and _log_name.startswith(
            "comfyui_image_scorer"
        ):
            _log._cache.clear()
