"""Class-based hardware tests demonstrating the class eyebrow in the Tests tab.

Tests grouped under a ``Test*`` class render the class name as a muted
"eyebrow" above the method name, instead of the raw ``Class::method`` string.
"""

from __future__ import annotations

import time

from pytest_reporter import fmt, step, substep


class TestPowerSupply:
    """Bench power-supply characterization across its output channels."""

    def test_channel_voltage_accuracy(self, log) -> None:
        log.info("Characterizing CH1 voltage accuracy")
        with step(fmt.text("Set ", fmt.mono("CH1.Voltage"), " to 3.3 V")):
            substep("Write setpoint over SCPI")
            substep(fmt.mono("SOUR1:VOLT 3.3"))
            time.sleep(0.01)
        with step("Measure output with the DMM"):
            substep("Read back voltage")
            with step("Compare against tolerance"):
                substep("Within +/- 1 percent")
        log.info("CH1 voltage within spec", data={"setpoint": 3.3, "measured": 3.301})

    def test_channel_current_limit(self, log) -> None:
        log.info("Verifying CH2 current limit trips correctly")
        with step("Configure CH2 current limit to 2 A"):
            substep(fmt.mono("SOUR2:CURR 2.0"))
        with step("Apply a 2.5 A load"):
            substep("Confirm the supply enters constant-current mode")
        time.sleep(0.01)

    def test_overvoltage_protection(self, log) -> None:
        log.info("Exercising OVP on CH3")
        with step("Arm overvoltage protection at 13 V"):
            substep(fmt.mono("SOUR3:VOLT:PROT 13"))
        with step("Ramp CH3 toward the trip point"):
            substep("Protection latches and output disables")
        time.sleep(0.01)
