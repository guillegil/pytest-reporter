# logger/logger.py
from datetime import datetime
from functools import wraps
import os
from logging import Logger

import logging

import pytest
import math

from pytest_report.meta import meta

datefmt = "%Y-%m-%d %H:%M:%S"

PASS_LEVEL = 25  # Between INFO (20) and WARNING (30)
FAIL_LEVEL = 35  # Between WARNING (30) and ERROR (40)
RW_LEVEL   = 26
RW_LEVEL_FAIL = 36

class BlockAllFilter(logging.Filter):
    def filter(self, record):
        return False

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
        RW_LEVEL:         "\033[37m",       # White
        RW_LEVEL_FAIL:    "\033[31m",       # Red
    }
    RESET = "\033[0m"

    def __init__(self, fmt=None, datefmt=None, style='%'):
        if fmt is None:
            fmt = "[%(asctime)s] %(levelname)-8s %(message)s"

        logging.addLevelName(PASS_LEVEL, "PASS")
        logging.addLevelName(FAIL_LEVEL, "FAIL")
        logging.addLevelName(RW_LEVEL,   "R/W OK")
        logging.addLevelName(RW_LEVEL_FAIL, "R/W FAIL")
        
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
        self.__file_handlers = {}
        self.__log_files = {}

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
    def handlers(self) -> list:
        return self.logger.handlers

    @property
    def cmd_handler(self) -> logging.StreamHandler | None:
        return self.__cmd_handler

    @cmd_handler.setter
    def cmd_handler(self, handler: logging.StreamHandler):
        self.__cmd_handler = handler

    def set_report_path(self, path: str):
        self.__report_path = path

    def set_level(self, level: int):
        self.__logger.setLevel(level)



    def debug(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.debug(msg, **kwargs)
            meta.append_logline(f"[DEBUG]   - {msg}")

    def info(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.info(msg, **kwargs)
            meta.append_logline(f"[INFO]    - {msg}")

    def warning(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.warning(msg, **kwargs)
            meta.append_logline(f"[WARNING] - {msg}")

    def error(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.error(msg, **kwargs)
            meta.append_logline(f"[ERROR]   - {msg}")

    def passed(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(PASS_LEVEL, msg, (), **kwargs)
            meta.append_logline(f"[PASSED]  - {msg}")

    def fail(self, *args, sep=' ', end='', enable=True, **kwargs):
        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(FAIL_LEVEL, msg, (), **kwargs)
            meta.append_logline(f"[FAIL]    - {msg}")
    
    def rw(
        self,
        *args,
        sep             : str        = ' ',
        end             : str        = '',
        reg_name        : str | None = None,
        write_data      : int | None = None,
        read_data       : int | None = None,
        enable          : bool       = True,
        do_assert       : bool       = False,
        
        **kwargs,
    ):
        msg: str = ""

        if enable:
            if (reg_name is not None) and (write_data is not None) and (read_data is not None):
                if write_data == read_data:
                    # Here and Write/Readback is OKAY
                    msg = f"Writing {reg_name} = "

                    if write_data < 0:
                        msg += write_data
                    else:
                        bitsize = math.ceil(math.log2(write_data)) // 4
                        
                    pass
                elif do_assert:
                    # Here there was an issue with the readback
                    pass
                else:
                    pass
            else:
                if args:  # Only log if there are arguments
                    msg = sep.join(str(a) for a in args) + end
                    # Correctly call the logger.info method
                    self.__logger._log(FAIL_LEVEL, msg, (), **kwargs)

            meta.append_logline(f"[R/W]     - {msg}")

    def configure_cmd_handler(self, level: int = logging.INFO, fmt: str = "[%(levelname)s] - %(message)s"):
        self.__cmd_handler = logging.StreamHandler()
        self.__cmd_handler.setLevel(level)
        self.__cmd_handler.setFormatter(ColorFormatter(fmt=fmt, datefmt=datefmt))
        self.__logger.addHandler(self.__cmd_handler)
    
    def configure_global_handler(self, level: int = logging.INFO, fmt: str = "%(asctime)s [%(levelname)s] - %(message)s"):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        filepath = os.path.join(self.report_path, f"{now}_all.log")

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        self.global_handler = logging.FileHandler(filepath, encoding="utf-8")
        self.global_handler.setLevel(level)
        self.global_handler.setFormatter(logging.Formatter(fmt))
        self.__logger.addHandler(self.global_handler)

    def configure_test_handler(
        self,
        level: int = INFO,
        filefmt: str = "%(asctime)s [%(levelname)s] - %(message)s"
    ):
        
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        filepath = os.path.join(self.report_path, f"{now}_X_{meta.current_filename}_{meta.current_testcase}.log")
    
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [%(levelname)s] - %(message)s"

        file_handler = logging.FileHandler(filename=filepath, encoding="utf-8")
        file_handler.setLevel(level)
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
        file_handler.setFormatter(logging.Formatter(fmt=filefmt, datefmt=datefmt))

        self.logger.addHandler(file_handler)

        if meta.current_filename not in self.__file_handlers:
            self.__file_handlers[meta.current_filename] = {}
        
        if meta.current_filename not in self.__log_files:
            self.__log_files[meta.current_filename] = {}

        if meta.current_testcase not in self.__log_files[meta.current_filename]:
            self.__log_files[meta.current_filename][meta.current_testcase] = {}

        self.__file_handlers[meta.current_filename][meta.current_testcase] = file_handler
        self.__log_files[meta.current_filename][meta.current_testcase]["call"] = filepath

        return file_handler

    def configure_test_setup_handler(
        self,
        level   : int = INFO, 
        filefmt : str = "%(asctime)s [SETUP] [%(levelname)s] - %(message)s"
    ):
        test_handler = self.__file_handlers.get(meta.current_filename, {}).get(meta.current_testcase, {})

        if test_handler:
            test_handler.addFilter(BlockAllFilter())
        
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        filepath = os.path.join(self.report_path, f"{now}_X_{meta.current_filename}_{meta.current_testcase}_setup.log")
        
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [SETUP] [%(levelname)s] - %(message)s"

        file_handler = logging.FileHandler(filename=filepath, encoding="utf-8")
        file_handler.setLevel(level)
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
        file_handler.setFormatter(logging.Formatter(fmt=filefmt, datefmt=datefmt))

        self.logger.addHandler(file_handler)

        if (meta.current_filename) not in self.__file_handlers:
            self.__file_handlers[meta.current_filename] = {}

        if meta.current_filename not in self.__log_files:
            self.__log_files[meta.current_filename] = {}
        
        if meta.current_testcase not in self.__log_files[meta.current_filename]:
            self.__log_files[meta.current_filename][meta.current_testcase] = {}

        self.__file_handlers[meta.current_filename][meta.current_testcase + "_setup"] = file_handler
        self.__log_files[meta.current_filename][meta.current_testcase]["setup"] = filepath

        return file_handler

    def test_setup(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_testproto = meta.current_testproto
            meta.current_testproto = "fake_setup"
            self.configure_test_setup_handler()
            result = func(*args, **kwargs)
            self.close_test_setup()
            meta.current_testproto = current_testproto
            return result
        
        return wrapper

    def close_test_setup(self):
        test_handler = self.__file_handlers.get(meta.current_filename, {}).get(meta.current_testcase, None)
        testsetup_handler = self.__file_handlers.get(meta.current_filename, {}).get(meta.current_testcase + "_setup", None)
        
        if test_handler is not None:
            test_handler.filters.clear()
        
        if testsetup_handler is not None:
            self.remove_file_handler(testsetup_handler)

        cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [%(levelname)s] - %(message)s"
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))

    def finish_current_test_log(self):
        test_handler = self.__file_handlers.get(meta.current_filename, {}).get(meta.current_testcase, None)
        self.remove_file_handler(test_handler)

        log_path_setup = self.__log_files[meta.current_filename][meta.current_testcase]["setup"]
        log_path_call  = self.__log_files[meta.current_filename][meta.current_testcase]["call"]

        status_key_setup = "_"
        status_key_call  = "_"

        if meta.current_test_info["setup"]["status"] == "passed":
            status_key_setup = "_P_"
        elif meta.current_test_info["setup"]["status"] == "failed":
            status_key_setup = "_F_"
        elif meta.current_test_info["setup"]["status"] == "error":
            status_key_setup = "_E_"
        elif meta.current_test_info["setup"]["status"] == "skipped":
            status_key_setup = "_S_"
        else:
            pass

        os.rename(log_path_setup, log_path_setup.replace("_X_", status_key_setup))

        if meta.current_test_info["call"]["status"] == "passed":
            status_key_call = "_P_"
        elif meta.current_test_info["call"]["status"] == "failed":
            status_key_call = "_F_"
        elif meta.current_test_info["call"]["status"] == "error":
            status_key_call = "_E_"
        elif meta.current_test_info["call"]["status"] == "skipped":
            status_key_call = "_S_"
        else:
            pass

        os.rename(log_path_call, log_path_call.replace("_X_", status_key_call))



    def remove_file_handler(self, handler):
        handler.close()
        log.logger.removeHandler(handler)


log = PytestLogger()
