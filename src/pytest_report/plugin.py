# pytest_reporter.py
import os
import pytest
import time  # Add this import
from .logger.logger import *
from .logger.logger import log
from .test_summary import TestResultTracker, TestSummaryDisplay, TestSessionInfo

from pytest import Session, Config, Item, CallInfo, Metafunc

# Global tracker, session info, and display instances
test_tracker = TestResultTracker()
session_info = TestSessionInfo()
test_summary_display = TestSummaryDisplay(test_tracker, session_info)


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


def _silence_terminal_writer(tw):
    """Apply silent patches to terminal writer."""
    if hasattr(tw, '_patched'):
        return
        
    tw._patched = True
    tw._original_write = tw.write
    tw._original_line = tw.line
    
    def silent_write(s, **kwargs):
        # Only allow test result markers (., F, E, s, x)
        s_str = str(s).strip()
        if s_str and not s_str.replace('.', '').replace('F', '').replace('E', '').replace('s', '').replace('x', ''):
            return tw._original_write(s, **kwargs)
    
    def silent_line(s='', **kwargs):
        # Suppress all line writes
        pass
    
    tw.write = silent_write
    tw.line = silent_line


def _silence_terminal_reporter(terminal):
    """Apply all patches to terminal reporter."""
    if not terminal:
        return
        
    # Silence basic output methods
    terminal.write = lambda *args, **kwargs: None
    terminal.write_line = lambda *args, **kwargs: None
    terminal.section = lambda *args, **kwargs: None
    terminal.write_sep = lambda *args, **kwargs: None
    
    # Silence collection-related methods
    terminal.report_collect = lambda *args, **kwargs: None
    terminal._printcollecteditems = lambda *args, **kwargs: None
    
    # Silence test execution output
    terminal.write_fspath_result = lambda *args, **kwargs: None
    terminal._write_progress_information_filling_space = lambda *args, **kwargs: None
    
    # Silence the terminal writer if it exists
    if hasattr(terminal, '_tw'):
        _silence_terminal_writer(terminal._tw)

@pytest.fixture(autouse=True)
def setup_test_logging(request):
    """Auto-fixture that configures logging for each test that actually runs."""
    
    # Check if this test function has log config info
    if hasattr(request.function, '_log_config'):
        config = request.function._log_config
        
        # Configure logging only once per test function (not per parameter)
        test_key = (config['filename'], config['testname'])
        if not hasattr(setup_test_logging, '_configured'):
            setup_test_logging._configured = set()
        
        if test_key not in setup_test_logging._configured:
            log.configure_test_handler(
                filename=config['filename'], 
                testname=config['testname']
            )
            setup_test_logging._configured.add(test_key)

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
    
    # Suppress pytest output
    config.option.tb = 'no'
    config.option.showlocals = False
    config.option.verbose = -1  # Quietest mode
    
    # Early terminal reporter patching
    terminal = config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        _silence_terminal_reporter(terminal)


# ===== SESSION START PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_report_header(config):
    """Remove pytest header."""
    return []


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: Session):
    """Ensure all output is suppressed at session start."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    _silence_terminal_reporter(terminal)


# ===== COLLECTION PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_collection(session):
    """Suppress output during collection phase."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    _silence_terminal_reporter(terminal)


def pytest_collection_modifyitems(config, items):
    """Store session information after collection."""
    session_info.set_session_data(config, items)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    """Display session header after collection and suppress collection finish output."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        terminal.report_collect = lambda *args, **kwargs: None
        # Display the session header here
        test_summary_display.display_header(terminal)


@pytest.hookimpl(tryfirst=True)
def pytest_report_collectionfinish(config, start_path, items):
    """Suppress collection summary."""
    return []


# ===== TEST GENERATION PHASE =====

def pytest_generate_tests(metafunc: Metafunc):
    """Configure logging setup to be done when test actually executes."""
    
    # Your existing parametrization logic here
    # metafunc.parametrize(...)
    
    # Add a fixture that will configure logging when the test runs
    if not hasattr(metafunc.function, '_log_configured'):
        # Mark that we've added the log setup to avoid duplicates
        metafunc.function._log_configured = True
        
        # Get test info
        base_testname = metafunc.function.__name__
        test_fname = os.path.basename(metafunc.function.__code__.co_filename)
        
        # Store the log config info on the function for later use
        metafunc.function._log_config = {
            'filename': test_fname,
            'testname': base_testname
        }
# ===== TEST EXECUTION PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Suppress per-test output during test protocol."""
    terminal = item.config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        terminal.write_fspath_result = lambda *args, **kwargs: None
        terminal._write_progress_information_filling_space = lambda *args, **kwargs: None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid, location):
    """Start timing the test."""
    test_tracker.start_test(nodeid)


def pytest_runtest_setup(item):
    """Add newline before each test (for your custom logging)."""
    print('\n')


def pytest_runtest_makereport(item: Item, call: CallInfo):
    """Capture test results for summary table."""
    if call.when == "call":  # Only capture the main test execution, not setup/teardown
        test_name = item.nodeid
        
        # Determine outcome based on call result
        if call.excinfo is None:
            outcome = "passed"
        elif call.excinfo[0] == pytest.skip.Exception:
            outcome = "skipped"
        else:
            outcome = "failed"
        
        # Add result with duration calculation
        test_tracker.add_result(test_name, outcome)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Hook for test teardown (currently unused)."""
    pass


# ===== SESSION FINISH PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: Session, exitstatus):
    """Hook for session finish (currently unused)."""
    pass


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Display custom results table."""
    test_summary_display.display_table(terminalreporter)