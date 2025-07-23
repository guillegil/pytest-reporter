# logger/logger.py
from datetime import datetime
from functools import wraps
import os
from logging import Logger

import logging

from pytest_report.meta import meta

import shutil

datefmt = "%Y-%m-%d %H:%M:%S"

STEP_LEVEL = 21
SUBSTEP_LEVEL = 22

PASS_LEVEL = 23  # Between INFO (20) and WARNING (30)
FAIL_LEVEL = 31  # Between WARNING (30) and ERROR (40)

RW_LEVEL         = 24
RW_LEVEL_SUBSTEP = 25

RW_LEVEL_FAIL = 32

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
        STEP_LEVEL:       "\033[37m",  # Same as INFO
        SUBSTEP_LEVEL:    "\033[37m",  # Same as INFO
        PASS_LEVEL:       "\033[1;30;42m",  # Bright Green
        FAIL_LEVEL:       "\033[1;97;41m",  # White on Red Background
        RW_LEVEL:         "\033[37m",       # White
        RW_LEVEL_FAIL:    "\033[31m",       # Red
    }
    RESET = "\033[0m"

    def __init__(self, fmt=None, datefmt=None, style='%'):
        if fmt is None:
            fmt = "[%(asctime)s] %(levelname)-8s %(message)s"

        logging.addLevelName(STEP_LEVEL,    "STEP")
        logging.addLevelName(SUBSTEP_LEVEL, "SUB-STEP")
        logging.addLevelName(PASS_LEVEL,    "PASS")
        logging.addLevelName(FAIL_LEVEL,    "FAIL")
        logging.addLevelName(RW_LEVEL,      "R/W OK")
        logging.addLevelName(RW_LEVEL_FAIL, "R/W FAILED")
        
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

        self.__setup_log_level = logging.INFO

        self.__report_path: str = ""

        self.__cmd_handler  = None

        self.__current_test_setup_handler = None
        self.__current_test_handler = None

        self.__current_setup_log_path = ""
        self.__current_call_log_path  = ""

        self.__step     : int = 0
        self.__substep  : int = 0

        self.__log_is_substep : bool = False

    @property
    def setup_log_level(self) -> int:
        return self.__setup_log_level

    @setup_log_level.setter
    def setup_log_level(self, level: int) -> None:
        self.__setup_log_level = level

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

    @property
    def current_test_handler(self) -> logging.StreamHandler | None:
        return self.__current_test_handler

    @current_test_handler.setter
    def current_test_handler(self, handler: logging.StreamHandler):
        self.__current_test_handler = handler

    @property
    def current_test_setup_handler(self) -> logging.StreamHandler | None:
        return self.__current_test_setup_handler

    @current_test_setup_handler.setter
    def current_test_setup_handler(self, handler: logging.StreamHandler):
        self.__current_test_setup_handler = handler

    @property
    def current_setup_log_path(self) -> str:
        return self.__current_setup_log_path

    @current_setup_log_path.setter
    def current_setup_log_path(self, path: str):
        self.__current_setup_log_path = path

    @property
    def current_call_log_path(self) -> str:
        return self.__current_call_log_path

    @current_call_log_path.setter
    def current_call_log_path(self, path: str):
        self.__current_call_log_path = path

    @property
    def stepn(self) -> int:
        return self.__step
    
    @stepn.setter
    def stepn(self, step: int) -> None:
        self.__step = step

    @property
    def substepn(self) -> int:
        return self.__substep
    
    @substepn.setter
    def substepn(self, substep: int) -> None:
        self.__substep = substep

    @property
    def log_is_substep(self) -> bool:
        return self.__log_is_substep
    
    @log_is_substep.setter
    def log_is_substep(self, is_substep: bool) -> None:
        self.__log_is_substep = is_substep

    def set_report_path(self, path: str):
        self.__report_path = path

    def set_level(self, level: int):
        self.__logger.setLevel(level)


    def debug(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": ""}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.debug(msg, **kwargs, extra=extra)
            meta.current_testlog = f"[DEBUG]   - {msg}"

    def info(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": ""}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.info(msg, **kwargs, extra=extra)
            meta.current_testlog = f"[INFO]    - {msg}"

    def warning(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": " "}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.warning(msg, **kwargs, extra=extra)
            meta.current_testlog = f"[WARNING] - {msg}"

    def error(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": ""}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger.error(msg, **kwargs, extra=extra)
            meta.current_testlog = f"[ERROR]   - {msg}"

    def passed(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": ""}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(PASS_LEVEL, msg, (), **kwargs, extra=extra)
            meta.current_testlog = f"[PASSED]  - {msg}"

    def fail(self, *args, sep=' ', end='', enable=True, **kwargs):
        extra = {"step": ""}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(FAIL_LEVEL, msg, (), **kwargs, extra=extra)
            meta.current_testlog = f"[FAIL]    - {msg}"
    
    def step(self, *args, sep=' ', end='', enable=True, **kwargs):
        self.stepn += 1
        self.substepn = 0
        extra = {"step": f" {self.stepn}"}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(STEP_LEVEL, msg, (), **kwargs, extra=extra)
            meta.current_testlog = f"[STEP {self.stepn}]    - {msg}"

    def substep(self, *args, sep=' ', end='', enable=True, **kwargs):
        self.substepn += 1
        extra = {"step": f" {self.stepn}.{self.substepn}"}

        if enable and args:  # Only log if enabled and there are arguments
            msg = sep.join(str(a) for a in args) + end
            # Correctly call the logger.info method
            self.__logger._log(SUBSTEP_LEVEL, msg, (), **kwargs, extra=extra)
            meta.current_testlog = f"[SUBSTEP {self.stepn}.{self.substepn}]    - {msg}"

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
        if self.log_is_substep:
            self.substepn += 1
            extra = {"step": f" {self.stepn}.{self.substepn}"}

        if enable:
            if (reg_name is not None) and (write_data is not None) and (read_data is not None):
                if write_data == read_data:
                    # Here and Write/Readback is OKAY

                    msg = f"{reg_name}: {write_data if write_data < 0 else f'{hex(write_data)}'} (Readback: {read_data if read_data < 0 else f'{hex(read_data)}'})"

                    self.__logger._log(RW_LEVEL, msg, (), **kwargs, extra=extra)

                else:
                    msg = f"{reg_name}: {write_data if write_data < 0 else f'{hex(write_data)}'} (Readback: {read_data if read_data < 0 else f'{hex(read_data)}'})"

                    self.__logger._log(RW_LEVEL_FAIL, msg, (), **kwargs, extra=extra)
            else:
                if args:  # Only log if there are arguments
                    msg = sep.join(str(a) for a in args) + end
                    # Correctly call the logger.info method
                    self.__logger._log(RW_LEVEL, msg, (), **kwargs, extra=extra)

            meta.current_testlog = f"[R/W]     - {msg}"

    def now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def configure_cmd_handler(
        self,
        level: int = logging.INFO,
        fmt: str = "[%(levelname)s%(step)s] - %(message)s"
    ):
        self.__cmd_handler = logging.StreamHandler()
        self.__cmd_handler.setLevel(level)
        self.__cmd_handler.setFormatter(ColorFormatter(fmt=fmt, datefmt=datefmt))
        self.__logger.addHandler(self.__cmd_handler)
    
    def configure_global_handler(
        self, 
        level: int = logging.INFO,
        fmt: str = "%(asctime)s [%(levelname)s%(step)s] - %(message)s"
    ):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        filepath = os.path.join(self.report_path, f"{now}_all.log")

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        self.global_handler = logging.FileHandler(filepath, encoding="utf-8")
        self.global_handler.setLevel(level)
        self.global_handler.setFormatter(logging.Formatter(fmt))
        self.__logger.addHandler(self.global_handler)

    def _generate_setup_log_path(self) -> str:
        filepath = os.path.join(self.report_path, f"{self.now()}_X_{meta.current_filename}_{meta.current_testcase}_setup_{meta.current_test_index}.log")

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        return filepath

    def _generate_call_log_path(self) -> str:
        filepath = os.path.join(self.report_path, f"{self.now()}_X_{meta.current_filename}_{meta.current_testcase}_{meta.current_test_index}.log")

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        return filepath

    def configure_setup_log(
        self,
        level   : int = INFO,
        filefmt : str = "%(asctime)s [%(levelname)s%(step)s] - %(message)s",
        **kwargs # For future use
    ):
        self.current_setup_log_path = self._generate_setup_log_path()

        # -- add the [SETUP] identificator to the CMD Logger ------------ #
        cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [SETUP][%(levelname)s%(step)s] - %(message)s"
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
        self.cmd_handler.setLevel(self.setup_log_level)

        # -- Configure a new File Handler ------------------------------- #
        self.current_test_setup_handler = logging.FileHandler(filename=self.current_setup_log_path, encoding="utf-8")
        self.current_test_setup_handler.setLevel(level)
        self.current_test_setup_handler.setFormatter(logging.Formatter(fmt=filefmt, datefmt=datefmt))

        # -- Add the handler to the global logger ----------------------- #
        self.logger.addHandler(self.current_test_setup_handler)

    def close_setup_log(self) -> None:
        self.remove_file_handler(self.current_test_setup_handler)

    def configuire_call_log(        
        self,
        level   : int = INFO,
        filefmt : str = "%(asctime)s [%(levelname)s%(step)s] - %(message)s",
        **kwargs # For future use) -> None:
    ):  
        self.current_call_log_path = self._generate_call_log_path()

        # -- add the [SETUP] identificator to the CMD Logger ------------ #
        cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [%(levelname)s%(step)s] - %(message)s"
        self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
        self.cmd_handler.setLevel(self.setup_log_level)

        # -- Configure a new File Handler ------------------------------- #
        self.current_test_handler = logging.FileHandler(filename=self.current_call_log_path, encoding="utf-8")
        self.current_test_handler.setLevel(level)
        self.current_test_handler.setFormatter(logging.Formatter(fmt=filefmt, datefmt=datefmt))

        # -- Add the handler to the global logger ----------------------- #
        self.logger.addHandler(self.current_test_handler)
  


    def test_setup(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_testproto = meta.current_testproto
            meta.current_testproto = "fake_setup"
            self.block_file_handler(self.current_test_handler)
            self.configure_setup_log()
            
            result = func(*args, **kwargs)
            
            self.remove_file_handler(self.current_test_setup_handler)
            self.release_file_handler(self.current_test_handler)
            meta.current_testproto = current_testproto

            cmdfmt = f"{meta.current_filename}/{meta.current_testcase} [%(levelname)s%(step)s] - %(message)s"
            self.cmd_handler.setFormatter(ColorFormatter(fmt=cmdfmt, datefmt=datefmt))
            self.cmd_handler.setLevel(self.setup_log_level)        

            return result
        
        return wrapper


    def release_file_handler(self, handler):
        if handler is not None:
            handler.filters.clear()

    def block_file_handler(self, handler):
        if handler is not None:
            handler.addFilter(BlockAllFilter())

    def remove_file_handler(self, handler):
        if handler is not None:
            handler.close()
            log.logger.removeHandler(handler)

    def close_all_logs(self):
        if self.current_test_handler is not None:
            self.remove_file_handler(self.current_test_handler)
        
        if self.current_test_setup_handler is not None:
            self.remove_file_handler(self.current_test_setup_handler)

        status_key_setup = "_"
        status_key_call  = "_"

        if meta.current_setup_status == "passed":
            status_key_setup = "_P_"
        elif meta.current_setup_status == "failed":
            status_key_setup = "_F_"
        elif meta.current_setup_status == "error":
            status_key_setup = "_E_"
        elif meta.current_setup_status == "skipped":
            status_key_setup = "_S_"
        else:
            status_key_setup = "_U_"

        if os.path.exists(self.current_setup_log_path):
            shutil.move(self.current_setup_log_path, self.current_setup_log_path.replace("_X_", status_key_setup))

        if meta.current_call_status == "passed":
            status_key_call = "_P_"
        elif meta.current_call_status == "failed":
            status_key_call = "_F_"
        elif meta.current_call_status == "error":
            status_key_call = "_E_"
        elif meta.current_call_status == "skipped":
            status_key_call = "_S_"
        else:
            status_key_setup = "_U_"

        if os.path.exists(self.current_call_log_path):
            shutil.move(self.current_call_log_path, self.current_call_log_path.replace("_X_", status_key_call))


log = PytestLogger()
