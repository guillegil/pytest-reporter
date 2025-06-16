# pytest_reporter.py
import os
import pytest
import time
from .logger.logger import *
from .logger.logger import log
from .test_summary import TestResultTracker, TestSummaryDisplay, TestSessionInfo

from pytest import Session, Config, Item, CallInfo, Metafunc

# Global tracker, session info, and display instances
test_tracker = TestResultTracker()
session_info = TestSessionInfo()
test_summary_display = TestSummaryDisplay(test_tracker, session_info)

_log_test_tracker = []

def __normalize_str(s: str) -> str:
    """Normalize string for log level comparison."""
    new_string: str = s.upper()
    new_string = new_string.replace(" ", "")
    new_string = new_string.replace("-", "")
    new_string = new_string.replace("_", "")
    return new_string


def _get_log_level(level_str: str):
    """Convert string log level to log constant."""
    level_map = {
        "INFO": log.INFO,
        "DEBUG": log.DEBUG,
        "WARNING": log.WARNING,
        "ERROR": log.ERROR,
        "CRITICAL": log.CRITICAL
    }
    normalized = __normalize_str(level_str)
    return level_map.get(normalized, log.INFO)


# ===== CONFIGURATION PHASE =====

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--reporter-log-path",
        action="store",
        default=os.path.join(".", "logs"),
        help="Path for log files"
    )
    
    parser.addoption(
        "--reporter-log-level",
        action="store",
        default="INFO",
        help="Set the logging level for the test session"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: Config):
    """Configure plugin and suppress pytest output early."""
    global test_tracker
    test_tracker.reset()  # Reset tracker for new session
    
    # Configure logging
    log_level = _get_log_level(config.getoption("--reporter-log-level"))
    log.set_level(log_level)

    if log.report_path == "":
        log.report_path = "./reports/logs"

    log.configure_cmd_handler(level=log_level)
    log.configure_global_handler(level=log_level)

    terminal = config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        # Modify verbosity or other settings
        terminal.verbosity = 0  # Reduce verbosity


# ===== SESSION START PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_report_header(config):
    """Remove pytest header."""
    return []


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: Session):
    """Ensure all output is suppressed at session start."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')


# ===== COLLECTION PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_collection(session):
    """Suppress output during collection phase."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')


def pytest_collection_modifyitems(config, items):
    """Store session information after collection."""
    session_info.set_session_data(config, items)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    """Display session header after collection and suppress collection finish output."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        test_summary_display.display_header(terminal)

@pytest.hookimpl(tryfirst=True)
def pytest_report_collectionfinish(config, start_path, items):
    """Suppress collection summary."""
    return []
    


# ===== TEST GENERATION PHASE =====

def pytest_generate_tests(metafunc: Metafunc):
    pass


# ===== TEST EXECUTION PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item: Item, nextitem):
    """Suppress per-test output during test protocol."""
    testname = item.originalname
    filename = item.fspath.basename

    global _log_test_tracker
    if testname not in _log_test_tracker:
        log.configure_test_handler(filename=filename, testname=testname)
        _log_test_tracker.append(testname)

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid, location):
    """Start timing the test."""
    test_tracker.start_test(nodeid)

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Add newline before each test (for your custom logging)."""
    print('\n')

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: Item, call: CallInfo):
    """Capture test results for summary table."""
    if call.when == "call":  # Only capture the main test execution, not setup/teardown
        test_name = item.nodeid

        # Determine outcome based on call result
        if call.excinfo is None:
            outcome = "passed"
        elif issubclass(call.excinfo.type, pytest.skip.Exception):
            outcome = "skipped"
        elif issubclass(call.excinfo.type, AssertionError):
            outcome = "failed"  # Test failure (assertion failed)
        else:
            outcome = "error"   # Test error (unexpected exception)

        # Add result with duration calculation
        test_tracker.add_result(test_name, outcome)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Hook for test teardown (currently unused)."""
    pass

@pytest.hookimpl
def pytest_report_teststatus(report, config):
    """Suppress short status indicators and capture skip reasons."""

    from pprint import pprint

    if report.when == "call":
        if report.passed:
            return "passed", "", ""
        elif report.failed:
            return "failed", "", ""
        elif report.skipped:
            # Get the skip reason
            skip_reason = ""
            if hasattr(report, 'longrepr') and report.longrepr:
                if len(report.longrepr) >= 3:
                    skip_test_filename = report.longrepr[0]
                    skip_test_fileline = report.longrepr[1]
                    skip_test_reason   = report.longrepr[2].replace("Skipped: ", "")
                else:
                    skip_test_filename = report.longrepr[0]
                    skip_test_fileline = report.longrepr[1]
                    skip_test_reason   = ""
                
                print(f"⏭️  \033[1;33mSKIPPED: {skip_test_filename} at line {skip_test_fileline} because: {skip_test_reason}\033[0m", end="")

            elif hasattr(report, 'wasxfail'):
                # For xfail cases
                skip_reason = getattr(report, 'wasxfail', '')
            else:
                pprint(report.__dict__)
            

            return "skipped", "", ""

    return None

# ===== SESSION FINISH PHASE =====

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: Session, exitstatus):
    """Session cleanup - called after all tests complete."""
    # Just do any necessary cleanup here
    pass

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_logreport(report):
    """Suppress detailed test failure output."""
    outcome = yield

    nodeid = report.nodeid

    if report.when == "call" and report.failed:
        # Get the terminal reporter from the session config
        # We need to access it differently
        pass  # Just suppress by not doing anything


    return outcome.get_result()

@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Display custom results table - called for terminal summary."""

    terminalreporter.stats.clear()

    # Display the summary table
    try:
        test_summary_display.display_table(terminalreporter)
    except Exception as e:
        # Fallback to direct print if there's an issue
        print(f"Error displaying summary table: {e}")
        print(f"Test results: {getattr(test_tracker, 'results', 'No results available')}")