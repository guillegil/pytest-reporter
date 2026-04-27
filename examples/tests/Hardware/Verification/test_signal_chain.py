"""Signal chain verification tests -- frequency response, SNR, distortion."""

from __future__ import annotations

import math
import random

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Simulated measurements
# ---------------------------------------------------------------------------

def _measure_gain_db(freq_hz: float, nominal_gain_db: float) -> float:
    """Simulate gain measurement with frequency-dependent roll-off."""
    # Roll off above 10 kHz (simulates filter)
    rolloff = 0.0
    if freq_hz > 10_000:
        rolloff = -20 * math.log10(freq_hz / 10_000)
    return round(nominal_gain_db + rolloff + random.gauss(0, 0.1), 3)


def _measure_snr_db() -> float:
    return round(random.uniform(58, 72), 2)


def _measure_thd_percent() -> float:
    return round(random.uniform(0.001, 0.05), 4)


def _measure_phase_deg(freq_hz: float) -> float:
    return round(-math.atan(freq_hz / 10_000) * 180 / math.pi + random.gauss(0, 0.5), 2)


# ---------------------------------------------------------------------------
# Gain flatness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "freq_hz",
    [100, 1_000, 5_000, 10_000, 20_000, 50_000, 100_000],
    ids=["100Hz", "1kHz", "5kHz", "10kHz", "20kHz", "50kHz", "100kHz"],
)
def test_gain_flatness(log, verify, testbench, freq_hz):
    """Verify amplifier gain is 20 dB ± 0.5 dB within passband."""
    sig = log.child("siggen")
    scope = log.child("scope")

    with step(f"Apply {freq_hz} Hz sine wave"):
        sig.info("Output configured", data={
            "frequency_hz": freq_hz, "amplitude_vpp": 0.1, "waveform": "sine",
        })

    with step("Measure output amplitude"):
        gain = _measure_gain_db(freq_hz, 20.0)
        scope.info("Gain measured", data={"gain_db": gain, "frequency_hz": freq_hz})

    step("Gain within ±0.5 dB of 20 dB",
         check=verify.approx(gain, 20.0, abs_tol=0.5, name=f"Gain @ {freq_hz} Hz", units="dB"))


# ---------------------------------------------------------------------------
# SNR
# ---------------------------------------------------------------------------


def test_signal_to_noise_ratio(log, verify, testbench):
    """Verify SNR exceeds 60 dB."""
    dmm = log.child("dmm")

    with step("Apply 1 kHz reference signal"):
        dmm.info("Signal: 1 kHz, 1 Vrms")

    with step("Measure noise floor"):
        snr = _measure_snr_db()
        dmm.info("SNR measured", data={"snr_db": snr})

    step("SNR above 60 dB",
         check=verify.greater(snr, 60.0, name="Signal-to-noise ratio", units="dB"))


# ---------------------------------------------------------------------------
# THD
# ---------------------------------------------------------------------------


def test_total_harmonic_distortion(log, verify, testbench):
    """Verify THD is below 0.1%."""
    scope = log.child("scope")

    with step("Apply 1 kHz test tone"):
        scope.info("Input: 1 kHz sine, 1 Vrms")

    with step("Perform FFT and measure harmonics"):
        thd = _measure_thd_percent()
        scope.info("THD result", data={
            "thd_percent": thd,
            "h2_db": round(-60 + random.gauss(0, 2), 1),
            "h3_db": round(-72 + random.gauss(0, 2), 1),
        })

    step("THD below 0.1%",
         check=verify.less(thd, 0.1, name="THD", units="%"))


# ---------------------------------------------------------------------------
# Phase response (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "freq_hz,max_phase_shift",
    [
        (100, -5.0),
        (1_000, -10.0),
        (10_000, -45.0),
        (50_000, -80.0),
    ],
    ids=["100Hz", "1kHz", "10kHz", "50kHz"],
)
def test_phase_response(log, verify, testbench, freq_hz, max_phase_shift):
    """Verify phase shift does not exceed limits at key frequencies."""
    sig = log.child("siggen")
    scope = log.child("scope")

    with step(f"Configure {freq_hz} Hz stimulus"):
        sig.info("Waveform applied", data={"freq": freq_hz, "amplitude": "100 mVpp"})

    phase = _measure_phase_deg(freq_hz)

    with step("Measure phase"):
        scope.info("Phase measurement", data={"phase_deg": phase, "freq_hz": freq_hz})

    step("Phase within limit",
         check=verify.greater(phase, max_phase_shift,
                              name=f"Phase @ {freq_hz} Hz", units="deg"))


# ---------------------------------------------------------------------------
# End-to-end signal chain test with artifacts
# ---------------------------------------------------------------------------


def test_signal_chain_end_to_end(log, verify, report_artifacts, testbench):
    """Full signal chain test: source → amplifier → filter → ADC.

    Saves a simulated waveform capture as an artifact.
    """
    sig = log.child("siggen")
    amp = log.child("amplifier")
    filt = log.child("filter")
    adc = log.child("adc")

    with step("Configure signal source"):
        sig.info("1 kHz sine, 100 mVpp, 50 ohm output")

    with step("Verify amplifier stage"):
        gain = _measure_gain_db(1_000, 20.0)
        amp.info("Gain measured", data={"gain_db": gain})
        substep("Check gain")

    step("Amplifier gain",
         check=verify.approx(gain, 20.0, abs_tol=0.5, name="Amp gain", units="dB"))

    with step("Verify filter response"):
        passband_gain = _measure_gain_db(1_000, 0.0)
        stopband_gain = _measure_gain_db(100_000, 0.0)
        filt.info("Passband", data={"gain_db": passband_gain, "freq": "1 kHz"})
        filt.info("Stopband", data={"gain_db": stopband_gain, "freq": "100 kHz"})

    step("Passband flat",
         check=verify.approx(passband_gain, 0.0, abs_tol=0.5, name="Filter passband", units="dB"))

    step("Stopband attenuation",
         check=verify.less(stopband_gain, -15.0, name="Filter stopband", units="dB"))

    with step("Verify ADC output"):
        snr = _measure_snr_db()
        thd = _measure_thd_percent()
        adc.info("ADC metrics", data={"snr_db": snr, "thd_pct": thd, "resolution_bits": 16})

    step("ADC SNR", check=verify.greater(snr, 60.0, name="ADC SNR", units="dB"))
    step("ADC THD", check=verify.less(thd, 0.1, name="ADC THD", units="%"))

    # Log signal chain summary as table
    log.table([
        {"Stage": "Amplifier", "Metric": "Gain", "Value": f"{gain:.1f} dB", "Limit": "20.0 +/- 0.5 dB"},
        {"Stage": "Filter", "Metric": "Passband", "Value": f"{passband_gain:.1f} dB", "Limit": "0.0 +/- 0.5 dB"},
        {"Stage": "Filter", "Metric": "Stopband", "Value": f"{stopband_gain:.1f} dB", "Limit": "< -15 dB"},
        {"Stage": "ADC", "Metric": "SNR", "Value": f"{snr:.1f} dB", "Limit": "> 60 dB"},
        {"Stage": "ADC", "Metric": "THD", "Value": f"{thd:.4f}%", "Limit": "< 0.1%"},
    ], name="signal_chain_summary")

    # Save simulated waveform data as artifact
    waveform_data = "time_us,voltage_mv\n"
    for i in range(200):
        t = i * 5.0
        v = round(1000 * math.sin(2 * math.pi * 1000 * t / 1e6) + random.gauss(0, 2), 2)
        waveform_data += f"{t},{v}\n"

    report_artifacts.mkdir(parents=True, exist_ok=True)
    (report_artifacts / "waveform_capture.csv").write_text(waveform_data)
    log.info("Waveform artifact saved", data={"file": "waveform_capture.csv", "points": 200})

    # Save a simple HTML summary as artifact
    html = """<!DOCTYPE html>
<html><head><title>Signal Chain Summary</title>
<style>body{font-family:sans-serif;padding:20px}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ccc;padding:8px;text-align:left}
th{background:#f5f5f5}.pass{color:green}.fail{color:red}</style></head>
<body><h2>Signal Chain Test Summary</h2>
<table><tr><th>Stage</th><th>Metric</th><th>Value</th><th>Limit</th></tr>
<tr><td>Amplifier</td><td>Gain</td><td>""" + f"{gain:.1f} dB" + """</td><td>20.0 ± 0.5 dB</td></tr>
<tr><td>Filter</td><td>Passband</td><td>""" + f"{passband_gain:.1f} dB" + """</td><td>0.0 ± 0.5 dB</td></tr>
<tr><td>Filter</td><td>Stopband</td><td>""" + f"{stopband_gain:.1f} dB" + """</td><td>&lt; -15 dB</td></tr>
<tr><td>ADC</td><td>SNR</td><td>""" + f"{snr:.1f} dB" + """</td><td>&gt; 60 dB</td></tr>
<tr><td>ADC</td><td>THD</td><td>""" + f"{thd:.4f}%" + """</td><td>&lt; 0.1%</td></tr>
</table></body></html>"""
    (report_artifacts / "signal_chain_summary.html").write_text(html)
    log.info("HTML summary artifact saved", data={"file": "signal_chain_summary.html"})


# ---------------------------------------------------------------------------
# Deliberate soft-assertion failures
# ---------------------------------------------------------------------------


def test_adc_linearity_check(log, verify, testbench):
    """ADC linearity test with several checks -- some deliberately failing."""
    adc = log.child("adc")

    with step("Sweep input voltage"):
        readings = []
        for vin_mv in [0, 500, 1000, 1500, 2000, 2500, 3000, 3300]:
            code = int(vin_mv / 3300 * 4095) + random.randint(-5, 5)
            readings.append((vin_mv, code))
            substep(f"Vin = {vin_mv} mV → code {code}")
            adc.info("Reading", data={"vin_mv": vin_mv, "adc_code": code})

    with step("Check linearity at key points"):
        linearity_rows = []
        for vin, code in readings:
            expected = int(vin / 3300 * 4095)
            error_lsb = abs(code - expected)
            linearity_rows.append({
                "Vin (mV)": vin, "Expected Code": expected,
                "Actual Code": code, "Error (LSB)": error_lsb,
                "Status": "PASS" if error_lsb <= 3 else "FAIL",
            })
            adc.info(f"Linearity @ {vin} mV", data={
                "expected": expected, "actual": code, "error_lsb": error_lsb,
            })
        adc.table(linearity_rows, name="adc_linearity_sweep")

    # Some of these may fail if random noise is large enough
    step("Zero-scale accuracy",
         check=verify.approx(readings[0][1], 0, abs_tol=3, name="Zero-scale code"))

    step("Mid-scale accuracy",
         check=verify.approx(readings[4][1], 2048, abs_tol=3, name="Mid-scale code"))

    step("Full-scale accuracy",
         check=verify.approx(readings[-1][1], 4095, abs_tol=3, name="Full-scale code"))


# ---------------------------------------------------------------------------
# xfail example
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="Known ADC crosstalk issue on CH3 above 50 kHz -- ticket #ADC-1192")
def test_crosstalk_rejection(log, verify, testbench):
    """Verify channel crosstalk is below -60 dB -- expected fail due to known issue."""
    scope = log.child("scope")

    with step("Drive CH1 with 50 kHz full-scale"):
        scope.info("CH1: 50 kHz, 3.3 Vpp")

    with step("Measure crosstalk on CH3"):
        crosstalk_db = round(-45 + random.gauss(0, 2), 1)
        scope.info("Crosstalk measured", data={"crosstalk_db": crosstalk_db, "frequency": "50 kHz"})

    step("Crosstalk below -60 dB",
         check=verify.less(crosstalk_db, -60.0, name="CH3 crosstalk", units="dB"))

    assert crosstalk_db < -60.0, f"Crosstalk {crosstalk_db} dB exceeds -60 dB limit"
