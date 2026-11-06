"""Class-based hardware tests demonstrating the class eyebrow in the Tests tab.

Tests grouped under a ``Test*`` class render the class name as a muted
"eyebrow" above the method name, instead of the raw ``Class::method`` string.
"""

from __future__ import annotations

import time

from stepdoc import step


class TestPowerSupply:
    """Bench power-supply characterization across its output channels."""

    def test_channel_voltage_accuracy(self, log) -> None:
        log.info("Characterizing CH1 voltage accuracy")
        with step("Set CH1.Voltage to 3.3 V"):
            with step("Write setpoint over SCPI"):
                pass
            with step("SOUR1:VOLT 3.3"):
                time.sleep(0.01)
        with step("Measure output with the DMM"):
            with step("Read back voltage"):
                with step("Compare against tolerance"):
                    with step("Within +/- 1 percent"):
                        pass
        log.info("CH1 voltage within spec", data={"setpoint": 3.3, "measured": 3.301})

    def test_channel_current_limit(self, log) -> None:
        log.info("Verifying CH2 current limit trips correctly")
        with step("Configure CH2 current limit to 2 A"):
            with step("SOUR2:CURR 2.0"):
                pass
        with step("Apply a 2.5 A load"):
            with step("Confirm the supply enters constant-current mode"):
                pass
        time.sleep(0.01)

    def test_overvoltage_protection(self, log) -> None:
        log.info("Exercising OVP on CH3")
        with step("Arm overvoltage protection at 13 V"):
            with step("SOUR3:VOLT:PROT 13"):
                pass
        with step("Ramp CH3 toward the trip point"):
            with step("Protection latches and output disables"):
                pass
        time.sleep(0.01)
