# Example integration in pytest plugin (pytest_reporter.py)
import os
import pytest
from .logger.logger import *
from .logger.logger import log


from pytest import Session, Config, Item, ExitCode, CallInfo, Metafunc


def __normalize_str(s: str) -> str:
    new_string: str = s.upper()
    new_string = s.replace(" ", "")
    new_string = s.replace("-", "")
    new_string = s.replace("_", "")

    return new_string


def pytest_addoption(parser):
    print("pytest_addoption")

    parser.addoption(
        "--reporter-log-path",
        action="store",
        default=os.path.join(".", "logs"),
        help=""
    )

    parser.addoption(
        "--reporter-log-level",
        action="store",
        default="INFO",
        help="Set the logging level for the test session (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )


def pytest_cmdline_main(config: Config):
    print("pytest_cmdline_mains")

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: Config):
    print("pytest_configure")

    log_level = __normalize_str( config.getoption("--reporter-log-level") )

    if log_level == "INFO":
        log_level = log.INFO
    elif log_level == "DEBUG":
        log_level = log.DEBUG
    elif log_level == "WARNING":
        log_level = log.WARNING
    elif log_level == "ERROR":
        log_level = log.ERROR
    elif log_level == "CRITICAL":
        log_level = log.CRITICAL
    else:
        log_level = log.INFO  # default fallback

    log.set_level(log_level)

    log.report_path = config.getoption("--reporter-log-path", default=os.path.join(".", "logs"))
    log.configure_cmd_handler(level=log_level)

def pytest_sessionstart(session: Session):
    print("pytest_sessionstart")

@pytest.hookimpl(trylast=True)
def pytest_generate_tests(metafunc: Metafunc):
    print("pytest_generate_tests")

    testname = metafunc.definition.originalname
    test_fname = os.path.basename(metafunc.function.__code__.co_filename)

    log.configure_test_handler(filename=test_fname, testname=testname)

def pytest_runtest_setup(item):
    print("pytest_runtest_setup")
    log.info("This is executed at the beggining ")

def pytest_runtest_makereport(item: Item, call: CallInfo):
    print("pytest_runtest_makereport")

@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    print("pytest_runtest_teardown")

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: Session, exitstatus):
    print("pytest_sessionfinish")

