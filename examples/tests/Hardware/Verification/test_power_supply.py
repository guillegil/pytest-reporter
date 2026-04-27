"""Power supply verification tests -- pytest-verify soft assertions + step(check=...)."""

from __future__ import annotations

import random
import time

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Simulated hardware
# ---------------------------------------------------------------------------

def _read_voltage(channel: int, nominal: float) -> float:
    """Simulate a PSU voltage reading with realistic noise."""
    return round(nominal + random.gauss(0, 0.005), 4)


def _read_current(channel: int, load_amps: float) -> float:
    """Simulate a PSU current reading."""
    return round(load_amps + random.gauss(0, 0.002), 4)


def _read_ripple_mv(channel: int) -> float:
    """Simulate ripple measurement in mV."""
    return round(random.uniform(3.0, 15.0), 2)


# ---------------------------------------------------------------------------
# Basic voltage verification
# ---------------------------------------------------------------------------


def test_3v3_rail_voltage(log, verify, testbench):
    """Verify 3.3 V rail is within tolerance under no-load conditions."""
    psu = log.child("psu")

    with step("Enable 3.3 V output"):
        psu.info("Setting CH1 to 3.3 V / 1 A limit")
        psu.info("Output enabled", data={"channel": 1, "voltage": 3.3, "current_limit": 1.0})

    with step("Wait for output to stabilize"):
        psu.info("Settling time: 100 ms")
        psu.debug("Waiting for capacitor charge cycle")

    voltage = _read_voltage(1, 3.3)

    with step("Measure output voltage"):
        psu.info("DMM reading", data={"voltage": voltage, "channel": 1})

    step("Verify voltage within ±50 mV",
         check=verify.approx(voltage, 3.3, abs_tol=0.05, name="CH1 voltage", units="V"))

    step("Verify voltage above minimum",
         check=verify.greater(voltage, 3.25, name="CH1 Vmin", units="V"))

    step("Verify voltage below maximum",
         check=verify.less(voltage, 3.35, name="CH1 Vmax", units="V"))


def test_5v_rail_voltage(log, verify, testbench):
    """Verify 5.0 V rail under load."""
    psu = log.child("psu")
    dmm = log.child("dmm")

    with step("Configure 5 V output"):
        psu.info("Setting CH2 to 5.0 V / 2 A limit")
        psu.info("Output enabled", data={"channel": 2, "voltage": 5.0, "current_limit": 2.0})

    with step("Apply 500 mA load"):
        psu.info("Electronic load set to 500 mA CC mode")
        dmm.info("Waiting for load transient to settle", data={"settle_ms": 200})

    voltage = _read_voltage(2, 5.0)
    current = _read_current(2, 0.5)

    with step("Read voltage and current"):
        dmm.info("Voltage", data={"reading": voltage, "units": "V"})
        dmm.info("Current", data={"reading": current, "units": "A"})

    step("Verify voltage ±100 mV",
         check=verify.approx(voltage, 5.0, abs_tol=0.1, name="CH2 voltage", units="V"))

    step("Verify load current",
         check=verify.approx(current, 0.5, abs_tol=0.01, name="CH2 current", units="A"))


def test_12v_rail_voltage(log, verify, testbench):
    """Verify 12 V rail accuracy."""
    psu = log.child("psu")

    with step("Configure 12 V output"):
        psu.info("Setting CH3 to 12.0 V / 3 A limit")
        psu.info("Output enabled", data={"channel": 3})

    voltage = _read_voltage(3, 12.0)

    with step("Read voltage"):
        psu.info("DMM reading", data={"voltage": voltage})

    step("Verify 12 V within ±1%",
         check=verify.approx(voltage, 12.0, rel_tol=0.01, name="CH3 voltage", units="V"))


# ---------------------------------------------------------------------------
# Parametrized multi-channel tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "channel,nominal_v,tolerance_v,load_a",
    [
        (1, 3.3, 0.05, 0.0),
        (1, 3.3, 0.05, 0.5),
        (1, 3.3, 0.05, 1.0),
        (2, 5.0, 0.10, 0.0),
        (2, 5.0, 0.10, 1.0),
        (2, 5.0, 0.10, 2.0),
        (3, 12.0, 0.24, 0.0),
        (3, 12.0, 0.24, 1.5),
        (3, 12.0, 0.24, 3.0),
    ],
    ids=[
        "3V3-no-load", "3V3-half-load", "3V3-full-load",
        "5V-no-load", "5V-half-load", "5V-full-load",
        "12V-no-load", "12V-half-load", "12V-full-load",
    ],
)
def test_voltage_regulation(log, verify, testbench, channel, nominal_v, tolerance_v, load_a):
    """Verify voltage regulation under varying load conditions."""
    psu = log.child("psu")

    with step(f"Configure CH{channel} to {nominal_v} V"):
        psu.info("Output configured", data={
            "channel": channel, "voltage": nominal_v, "current_limit": load_a + 0.5,
        })

    if load_a > 0:
        with step(f"Apply {load_a} A load"):
            psu.info("Electronic load enabled", data={"mode": "CC", "setpoint_a": load_a})

    voltage = _read_voltage(channel, nominal_v)

    with step("Measure output"):
        psu.info("Reading", data={"voltage": voltage, "channel": channel})

    step("Voltage within tolerance",
         check=verify.approx(voltage, nominal_v, abs_tol=tolerance_v,
                             name=f"CH{channel} @ {load_a}A", units="V"))


# ---------------------------------------------------------------------------
# Ripple / noise
# ---------------------------------------------------------------------------


def test_output_ripple_3v3(log, verify, testbench):
    """Verify output ripple on 3.3 V rail is below 20 mV peak-to-peak."""
    scope = log.child("scope")

    with step("Configure scope for ripple measurement"):
        scope.info("Channel 1: AC coupling, 5 mV/div, 20 MHz bandwidth limit")
        scope.info("Trigger: auto, falling edge, 10 mV threshold")
        scope.info("Timebase: 10 us/div")

    ripple = _read_ripple_mv(1)

    with step("Capture waveform"):
        scope.info("Acquired 10000 points", data={"sample_rate": "2 GSa/s"})
        scope.info("Ripple measurement", data={"peak_to_peak_mv": ripple})

    step("Ripple below 20 mV",
         check=verify.less(ripple, 20.0, name="CH1 ripple Vpp", units="mV"))


def test_output_ripple_5v(log, verify, testbench):
    """Verify output ripple on 5 V rail is below 30 mV peak-to-peak."""
    scope = log.child("scope")

    with step("Configure scope for CH2 ripple"):
        scope.info("AC coupling, 10 mV/div, 20 MHz BW limit")

    ripple = _read_ripple_mv(2)

    with step("Capture waveform"):
        scope.info("Measurement", data={"ripple_mv": ripple})

    step("Ripple below 30 mV",
         check=verify.less(ripple, 30.0, name="CH2 ripple Vpp", units="mV"))


# ---------------------------------------------------------------------------
# Current limiting
# ---------------------------------------------------------------------------


def test_overcurrent_protection(log, verify, testbench):
    """Verify OCP trips when load exceeds channel limit."""
    psu = log.child("psu")

    with step("Set CH1 current limit to 1 A"):
        psu.info("OCP configured", data={"channel": 1, "limit_a": 1.0, "mode": "fold-back"})

    with step("Ramp load to 1.2 A"):
        for load in [0.5, 0.8, 1.0, 1.1, 1.2]:
            substep(f"Load = {load} A")
            psu.info("Load step", data={"load_a": load})

    with step("Check OCP triggered"):
        ocp_tripped = True
        psu.warning("OCP activated", data={"channel": 1, "trip_current_a": 1.05})

    step("OCP triggered",
         check=verify.is_true(ocp_tripped, name="CH1 OCP status"))


# ---------------------------------------------------------------------------
# Skip and xfail
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="High-voltage test requires safety interlock not available in CI")
def test_48v_rail_voltage(log, verify, testbench):
    """Verify 48 V rail for PoE applications."""
    log.info("This should not execute")


@pytest.mark.xfail(reason="Known firmware bug #PSU-2847 causes 2% overshoot on fast load step")
def test_load_transient_response(log, verify, testbench):
    """Verify transient response on fast load step -- expected to fail due to firmware bug."""
    psu = log.child("psu")
    scope = log.child("scope")

    with step("Configure load step"):
        psu.info("CH1 at 3.3 V, 1 A limit")
        scope.info("Trigger on CH1 falling edge, 50 mV threshold")

    with step("Apply 0-to-1A step in 1 us"):
        psu.info("Load step applied", data={"from_a": 0, "to_a": 1.0, "slew_us": 1})
        scope.info("Transient captured", data={"undershoot_mv": 85, "recovery_us": 120})

    undershoot_mv = 85.0

    step("Undershoot below 50 mV",
         check=verify.less(undershoot_mv, 50.0, name="Load transient undershoot", units="mV"))

    assert undershoot_mv < 50.0, f"Undershoot {undershoot_mv} mV exceeds 50 mV limit"


# ---------------------------------------------------------------------------
# Deliberate failure for report demonstration
# ---------------------------------------------------------------------------


def test_efficiency_at_full_load(log, verify, testbench):
    """PSU efficiency must be above 90% at full load -- deliberate soft-assertion failure."""
    psu = log.child("psu")

    with step("Measure input power"):
        input_power = 42.5
        psu.info("Input power", data={"watts": input_power})

    with step("Measure output power"):
        output_power = 36.8
        psu.info("Output power", data={"watts": output_power})

    efficiency = round(output_power / input_power * 100, 2)

    with step("Calculate efficiency"):
        psu.info("Efficiency", data={"percent": efficiency})

    step("Efficiency above 90%",
         check=verify.greater(efficiency, 90.0, name="Full-load efficiency", units="%"))

    step("Output power above 38 W",
         check=verify.greater(output_power, 38.0, name="Output power", units="W"))


def test_all_channels_in_range(log, verify, testbench):
    """Verify all channels simultaneously -- mixed pass/fail checks."""
    psu = log.child("psu")

    with step("Enable all channels"):
        psu.info("All outputs enabled")

    readings = {
        1: _read_voltage(1, 3.3),
        2: _read_voltage(2, 5.0),
        3: _read_voltage(3, 12.0),
    }

    with step("Read all channels"):
        for ch, v in readings.items():
            substep(f"CH{ch} = {v} V")
            psu.info(f"CH{ch} reading", data={"voltage": v})

    nominals = {1: 3.3, 2: 5.0, 3: 12.0}
    tolerances = {1: 0.05, 2: 0.10, 3: 0.24}
    psu.table(
        [{"Channel": f"CH{ch}", "Nominal (V)": nominals[ch],
          "Measured (V)": readings[ch],
          "Error (mV)": round((readings[ch] - nominals[ch]) * 1000, 1),
          "Tolerance (mV)": tolerances[ch] * 1000,
          "Status": "PASS" if abs(readings[ch] - nominals[ch]) <= tolerances[ch] else "FAIL"}
         for ch in readings],
        name="channel_summary",
    )

    step("CH1 in range [3.25, 3.35] V",
         check=verify.between(readings[1], 3.25, 3.35, name="CH1 range", units="V"))

    step("CH2 in range [4.90, 5.10] V",
         check=verify.between(readings[2], 4.90, 5.10, name="CH2 range", units="V"))

    step("CH3 in range [11.76, 12.24] V",
         check=verify.between(readings[3], 11.76, 12.24, name="CH3 range", units="V"))
