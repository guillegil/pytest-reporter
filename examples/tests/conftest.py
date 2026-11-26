"""Session-scoped fixtures for the example test suite."""

from __future__ import annotations

import logging
import random
import time

import pytest


def pytest_sessionstart(session) -> None:
    """Logging outside the tests goes to the report's Session Logs tab."""
    lab = logging.getLogger("lab")
    lab.info("Lab bench session started", extra={"bench": "B-07", "operator": "ci"})
    lab.getChild("inventory").info("Instruments reserved", extra={"count": 4})


def pytest_reporter_seed() -> int:
    """Demonstrate the manual RNG seed override shown in Run Information."""
    return 1337


@pytest.fixture(scope="session")
def testbench():
    """Simulate a hardware testbench with instrument discovery."""
    tb = logging.getLogger("testbench")
    tb.info("Starting testbench initialization")
    tb.info("Scanning GPIB bus for instruments")

    psu = tb.getChild("psu")
    psu.info("Connecting to PSU", extra={"address": "TCPIP::192.168.1.10", "port": 5025})
    psu.info("Identification query sent")
    psu.info("Connected", extra={"model": "Keysight E36312A", "firmware": "2.1.0", "serial": "MY56001234"})
    psu.info("Self-test passed", extra={"result": "0,No error"})
    psu.info("Output channels configured", extra={"ch1": "3.3V/1A", "ch2": "5.0V/2A", "ch3": "12V/3A"})

    scope = tb.getChild("scope")
    scope.info("Connecting to oscilloscope", extra={"address": "TCPIP::192.168.1.11", "port": 5025})
    scope.info("Connected", extra={"model": "Keysight MSOX3104T", "firmware": "7.40", "serial": "MY57009876"})
    scope.info("Calibration check", extra={"status": "passed", "last_cal": "2026-01-15"})
    scope.info("Channel configuration", extra={
        "ch1": {"coupling": "DC", "scale": "1V/div", "probe": "10x"},
        "ch2": {"coupling": "DC", "scale": "500mV/div", "probe": "1x"},
    })

    dmm = tb.getChild("dmm")
    dmm.info("Connecting to DMM", extra={"address": "TCPIP::192.168.1.12", "port": 5025})
    dmm.info("Connected", extra={"model": "Keysight 34461A", "firmware": "A.03.01", "serial": "MY58005555"})
    dmm.info("Range set to auto")

    siggen = tb.getChild("siggen")
    siggen.info("Connecting to signal generator", extra={"address": "TCPIP::192.168.1.13"})
    siggen.info("Connected", extra={"model": "Keysight 33600A", "firmware": "5.10", "serial": "MY59001111"})
    siggen.info("Output impedance set to 50 ohm")

    tb.info("All instruments discovered and initialized", extra={"instrument_count": 4})

    yield {
        "psu": {"model": "E36312A", "channels": 3},
        "scope": {"model": "MSOX3104T", "channels": 4},
        "dmm": {"model": "34461A"},
        "siggen": {"model": "33600A"},
    }

    tb.info("Starting testbench teardown")
    psu.info("Disabling all outputs")
    scope.info("Resetting to default state")
    dmm.info("Disconnecting")
    siggen.info("Output disabled, disconnecting")
    tb.info("Testbench teardown complete")


@pytest.fixture(scope="session")
def db_pool():
    """Simulate a database connection pool."""
    db = logging.getLogger("database")
    db.info("Creating connection pool", extra={"host": "db.internal", "port": 5432, "database": "testdb"})
    db.info("Pool created", extra={"min_connections": 2, "max_connections": 10})
    db.info("Running schema migration check")
    db.info("Schema is up to date", extra={"version": "2026.03.28.001"})

    yield {"host": "db.internal", "pool_size": 10}

    db.info("Draining connection pool")
    db.info("All connections closed")


@pytest.fixture(scope="session")
def redis_client():
    """Simulate a Redis connection."""
    cache = logging.getLogger("redis")
    cache.info("Connecting to Redis", extra={"host": "redis.internal", "port": 6379})
    cache.info("Connected", extra={"version": "7.2.4", "mode": "standalone"})
    cache.info("Flushing test database", extra={"db": 1})

    yield {"host": "redis.internal", "db": 1}

    cache.info("Disconnecting from Redis")


# --- Flaky counter for retry demonstration ---
_flaky_counters: dict[str, int] = {}


@pytest.fixture
def flaky_service():
    """Simulate a service that fails intermittently."""

    def call(name: str, fail_first: int = 1) -> str:
        _flaky_counters.setdefault(name, 0)
        _flaky_counters[name] += 1
        if _flaky_counters[name] <= fail_first:
            raise ConnectionError(f"Service '{name}' temporarily unavailable (attempt {_flaky_counters[name]})")
        return f"ok:{name}"

    return call
