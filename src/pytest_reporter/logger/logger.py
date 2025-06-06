# logger/logger.py
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from logging import Logger, LoggerAdapter

import logging
from functools import wraps
from re import DEBUG



datefmt = "%Y-%m-%d %H:%M:%S"

PASS_LEVEL = 25  # Between INFO (20) and WARNING (30)
FAIL_LEVEL = 35  # Between WARNING (30) and ERROR (40)

class ColorFormatter(logging.Formatter):
    # ANSI escape sequences for colors
    COLORS = {
        logging.DEBUG:    "\033[36m",  # Cyan
        logging.INFO:     "\033[37m",  # White
        logging.WARNING:  "\033[33m",  # Yellow
        logging.ERROR:    "\033[31m",  # Red
        logging.CRITICAL: "\033[91m",  # Bright Red
        PASS_LEVEL:       "\033[1;30;42m",  # Bright Green
        FAIL_LEVEL:       "\033[1;97;41m",  # White on Red Background
    }
    RESET = "\033[0m"

    def __init__(self, fmt=None, datefmt=None, style='%'):
        if fmt is None:
            fmt = "[%(asctime)s] %(levelname)-8s %(message)s"

        logging.addLevelName(PASS_LEVEL, "PASS")
        logging.addLevelName(FAIL_LEVEL, "FAIL")

        super().__init__(fmt, datefmt, style)

    def format(self, record):
        # Get original formatted message
        formatted = super().format(record)
        # Select color based on level
        color = self.COLORS.get(record.levelno, self.RESET)
        # Wrap the entire line in color, then reset
        return f"{color}{formatted}{self.RESET}"



class PytestLogger:

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL    

    def __init__(self, *args, **kwargs):
        self.__logger = logging.getLogger("pytest_logger")
        self.__logger.setLevel(logging.INFO)

        self.__report_path: str = ""

        self.__cmd_handler  = None
        self.__file_handler = None

    @property
    def report_path(self) -> str:
        return self.__report_path

    @report_path.setter
    def report_path(self, path: str) -> None:
        self.__report_path = path

    @property
    def logger(self) -> Logger:
        return self.__logger

    @property
    def cmd_handler(self) -> logging.StreamHandler | None:
        return self.__cmd_handler

    @cmd_handler.setter
    def cmd_handler(self, handler: logging.StreamHandler):
        self.__cmd_handler = handler

    @property
    def file_handler(self) -> logging.FileHandler | None:
        return self.__file_handler

    @file_handler.setter
    def file_handler(self, handler: logging.FileHandler):
        self.__file_handler = handler

    def set_level(self, level: int):
        self.__logger.setLevel(level)


    def debug(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.debug(msg, **kwargs)

    def info(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.info(msg, **kwargs)

    def warning(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.warning(msg, **kwargs)

    def error(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.error(msg, **kwargs)

    def passed(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(PASS_LEVEL, msg, (), **kwargs)

    def fail(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(FAIL_LEVEL, msg, (), **kwargs)

    def configure_cmd_handler(self, level: int = logging.INFO, fmt: str = "[%(levelname)s] - %(message)s"):
        self.__cmd_handler = logging.StreamHandler()
        self.__cmd_handler.setLevel(level)
        self.__cmd_handler.setFormatter(ColorFormatter(fmt=fmt, datefmt=datefmt))
        self.__logger.addHandler(self.__cmd_handler)
    
    def configure_global_handler(self, filename: str, level: int = logging.INFO, fmt: str = "%(asctime)s [%(levelname)s] - %(message)s"):
        if not os.path.exists(filename):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        self.global_handler = logging.FileHandler(filename)
        self.global_handler.setLevel(level)
        self.global_handler.setFormatter(logging.Formatter(fmt))
        self.__logger.addHandler(self.global_handler)

    def configure_test_handler(self, filename: str, testname: str, level: int = INFO, filefmt: str = "%(asctime)s [%(levelname)s] - %(message)s"):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        filepath = os.path.join(self.report_path, f"{now}_{filename}_{testname}.log")
        
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        cmdfmt = f"{filename}/{testname} [%(levelname)s] - %(message)s"

        self.file_handler = logging.FileHandler(filename=filepath)
        self.file_handler.setLevel(level)
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
        self.file_handler.setFormatter(logging.Formatter(fmt=filefmt, datefmt=datefmt))

        self.logger.addHandler(self.file_handler)


log = PytestLogger()
