"""DAC sweep with all three integrations: pytest-strategies rows, stepdoc steps, verify checks.

Each row is a test of its own (``test_dac_linearity[directed-zero]``,
``[rand-1]``, ...). The report shows the row and its seed on the Summary tab,
the steps (with the verify checks placed in them) on the Procedure tab, and the
checks as verification cards.
"""

from __future__ import annotations

import random

import stepdoc
from pytest_strategy import Parameter, RNGInteger, TestArg, register, strategy
from stepdoc import step


@register("dac_codes")
def dac_codes() -> Parameter:
    return Parameter(
        TestArg("code", rng_type=RNGInteger(0, 4095), description="DAC code"),
        directed_vectors={"zero": {"code": 0}, "full_scale": {"code": 4095}},
    )


class _Dac:
    """A simulated 12-bit DAC driving a 3.3 V reference, with a small offset."""

    def __init__(self) -> None:
        self._code = 0

    def write(self, code: int) -> None:
        stepdoc.record_action("dac.code", "write", code, value_from=("code",))
        self._code = code

    def measure(self) -> float:
        volts = round(self._code * 3.3 / 4095 + random.gauss(0, 0.0002), 5)
        stepdoc.record_action("dmm.voltage", "measure", volts, unit="V")
        return volts


@strategy("dac_codes")
def test_dac_linearity(log, verify, code: int) -> None:
    """The output follows the code within half an LSB-ish (1 mV)."""
    dac = _Dac()
    with step("Program the DAC"):
        dac.write(code)
        log.info("Code written", data={"code": code})

    with step("Measure the output"):
        volts = dac.measure()
        expected = code * 3.3 / 4095
        verify.approx(volts, expected, abs_tol=0.001, name="Vout", units="V")
