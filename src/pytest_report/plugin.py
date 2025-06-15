# pytest_reporter.py
import os
import pytest
from .logger.logger import *
from .logger.logger import log

from pytest import Session, Config, Item, CallInfo, Metafunc


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
    """Hook for modifying collected items (currently unused)."""
    pass


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    """Suppress collection finish output."""
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    if terminal:
        terminal.report_collect = lambda *args, **kwargs: None


@pytest.hookimpl(tryfirst=True)
def pytest_report_collectionfinish(config, start_path, items):
    """Suppress collection summary."""
    return []


# ===== TEST GENERATION PHASE =====

@pytest.hookimpl(trylast=True)
def pytest_generate_tests(metafunc: Metafunc):
    """Configure test-specific logging."""
    testname = metafunc.definition.originalname
    test_fname = os.path.basename(metafunc.function.__code__.co_filename)
    log.configure_test_handler(filename=test_fname, testname=testname)


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
    """Suppress test start logging."""
    pass


def pytest_runtest_setup(item):
    """Add newline before each test (for your custom logging)."""
    print('\n')


def pytest_runtest_makereport(item: Item, call: CallInfo):
    """Hook for creating test reports (currently unused)."""
    pass


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Hook for test teardown (currently unused)."""
    pass


# ===== SESSION FINISH PHASE =====

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: Session, exitstatus):
    """Hook for session finish (currently unused)."""
    pass


@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Provide minimal terminal summary."""
    terminalreporter._tw.line("")