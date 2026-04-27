"""Thermal measurement tests -- artifacts, session_log, xfail, skip, verify."""

from __future__ import annotations

import json
import math
import random

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Simulated sensors
# ---------------------------------------------------------------------------

def _read_temperature(sensor: str, ambient: float = 25.0) -> float:
    """Simulate a temperature reading in Celsius."""
    offsets = {"cpu": 35.0, "gpu": 40.0, "vrm": 28.0, "ambient": 0.0, "heatsink": 15.0}
    return round(ambient + offsets.get(sensor, 10.0) + random.gauss(0, 0.5), 2)


def _read_fan_rpm(fan: str) -> int:
    speeds = {"cpu_fan": 1800, "case_fan_1": 1200, "case_fan_2": 1200, "psu_fan": 900}
    return speeds.get(fan, 1000) + random.randint(-50, 50)


# ---------------------------------------------------------------------------
# Basic thermal tests with verify
# ---------------------------------------------------------------------------


def test_cpu_temperature_idle(log, verify, testbench):
    """Verify CPU temperature at idle is within safe limits."""
    thermal = log.child("thermal")

    with step("Read ambient temperature"):
        ambient = _read_temperature("ambient")
        thermal.info("Ambient", data={"temp_c": ambient})

    with step("Read CPU temperature"):
        cpu_temp = _read_temperature("cpu")
        thermal.info("CPU temperature", data={"temp_c": cpu_temp, "state": "idle"})

    step("CPU temp below 70 °C",
         check=verify.less(cpu_temp, 70.0, name="CPU idle temp", units="°C"))

    step("CPU temp above ambient",
         check=verify.greater(cpu_temp, ambient, name="CPU > ambient", units="°C"))


def test_gpu_temperature_under_load(log, verify, testbench):
    """Verify GPU temperature under synthetic load."""
    thermal = log.child("thermal")

    with step("Apply GPU stress test"):
        thermal.info("Starting FurMark 30-second burn")
        for sec in [5, 10, 15, 20, 25, 30]:
            substep(f"t = {sec}s")
            temp = _read_temperature("gpu") + sec * 0.3
            thermal.info("GPU temp", data={"temp_c": round(temp, 1), "elapsed_s": sec})

    final_temp = round(_read_temperature("gpu") + 9.0, 1)

    with step("Read final temperature"):
        thermal.info("Final GPU temperature", data={"temp_c": final_temp})

    step("GPU below 85 °C after stress",
         check=verify.less(final_temp, 85.0, name="GPU stress temp", units="°C"))


# ---------------------------------------------------------------------------
# Fan speed tests with artifacts
# ---------------------------------------------------------------------------


def test_fan_speeds_and_report(log, verify, report_artifacts):
    """Verify fan speeds and save a JSON report as artifact."""
    cooling = log.child("cooling")

    fans = ["cpu_fan", "case_fan_1", "case_fan_2", "psu_fan"]
    readings = {}

    with step("Read all fan speeds"):
        for fan in fans:
            rpm = _read_fan_rpm(fan)
            readings[fan] = rpm
            substep(f"{fan}: {rpm} RPM")
            cooling.info(f"{fan} speed", data={"rpm": rpm})

    step("CPU fan above 1500 RPM",
         check=verify.greater(readings["cpu_fan"], 1500, name="CPU fan speed", units="RPM"))

    step("Case fan 1 above 1000 RPM",
         check=verify.greater(readings["case_fan_1"], 1000, name="Case fan 1", units="RPM"))

    step("PSU fan above 700 RPM",
         check=verify.greater(readings["psu_fan"], 700, name="PSU fan speed", units="RPM"))

    # Log fan readings as a table
    cooling.table(
        [{"Fan": fan, "RPM": rpm, "Status": "OK" if rpm > 700 else "WARNING"}
         for fan, rpm in readings.items()],
        name="fan_speed_readings",
    )

    # Save fan speed report as artifact
    report_artifacts.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": "2026-04-04T12:00:00Z",
        "readings": {fan: {"rpm": rpm, "status": "ok" if rpm > 700 else "warning"}
                     for fan, rpm in readings.items()},
    }
    (report_artifacts / "fan_speeds.json").write_text(json.dumps(report, indent=2))
    cooling.info("Fan report artifact saved")


# ---------------------------------------------------------------------------
# Thermal profile with HTML artifact
# ---------------------------------------------------------------------------


def test_thermal_profile(log, verify, report_artifacts, testbench):
    """Run a thermal profile test and generate an HTML artifact with inline chart."""
    thermal = log.child("thermal")

    profile = []
    with step("Run 60-second thermal profile"):
        for t in range(0, 61, 5):
            cpu = _read_temperature("cpu") + t * 0.15
            gpu = _read_temperature("gpu") + t * 0.20
            profile.append({"time_s": t, "cpu_c": round(cpu, 1), "gpu_c": round(gpu, 1)})
            if t % 15 == 0:
                substep(f"t={t}s: CPU={cpu:.1f}°C, GPU={gpu:.1f}°C")
                thermal.info("Sample", data=profile[-1])

    # Log the full profile as a table
    thermal.table(profile, name="thermal_profile")

    max_cpu = max(p["cpu_c"] for p in profile)
    max_gpu = max(p["gpu_c"] for p in profile)

    step("Peak CPU temp below 80 °C",
         check=verify.less(max_cpu, 80.0, name="Peak CPU temp", units="°C"))

    step("Peak GPU temp below 90 °C",
         check=verify.less(max_gpu, 90.0, name="Peak GPU temp", units="°C"))

    # Generate HTML artifact with embedded SVG chart
    report_artifacts.mkdir(parents=True, exist_ok=True)

    times = [p["time_s"] for p in profile]
    cpus = [p["cpu_c"] for p in profile]
    gpus = [p["gpu_c"] for p in profile]
    y_min = int(min(min(cpus), min(gpus)) - 5)
    y_max = int(max(max(cpus), max(gpus)) + 5)

    def _scale_x(t: float) -> float:
        return 60 + (t / 60) * 480

    def _scale_y(v: float) -> float:
        return 260 - ((v - y_min) / (y_max - y_min)) * 220

    cpu_points = " ".join(f"{_scale_x(t)},{_scale_y(c)}" for t, c in zip(times, cpus))
    gpu_points = " ".join(f"{_scale_x(t)},{_scale_y(g)}" for t, g in zip(times, gpus))

    html = f"""<!DOCTYPE html>
<html><head><title>Thermal Profile</title>
<style>body{{font-family:sans-serif;padding:20px;background:#0B1120;color:#E8ECF4}}
svg{{background:#131C2E;border-radius:8px}}
.label{{fill:#8292AA;font-size:11px}}</style></head>
<body><h2>Thermal Profile (60s)</h2>
<svg width="600" height="300" viewBox="0 0 600 300">
  <line x1="60" y1="260" x2="540" y2="260" stroke="#1E2D45"/>
  <line x1="60" y1="40" x2="60" y2="260" stroke="#1E2D45"/>
  <text x="300" y="290" text-anchor="middle" class="label">Time (s)</text>
  <text x="15" y="150" text-anchor="middle" transform="rotate(-90,15,150)" class="label">Temp (°C)</text>
  <polyline points="{cpu_points}" fill="none" stroke="#EF4444" stroke-width="2"/>
  <polyline points="{gpu_points}" fill="none" stroke="#F59E0B" stroke-width="2"/>
  <text x="545" y="20" class="label">CPU (red)</text>
  <text x="545" y="35" class="label">GPU (amber)</text>
  <text x="60" y="275" class="label">0</text>
  <text x="540" y="275" class="label">60</text>
  <text x="50" y="265" text-anchor="end" class="label">{y_min}</text>
  <text x="50" y="45" text-anchor="end" class="label">{y_max}</text>
</svg>
<p>Peak CPU: {max_cpu:.1f}°C | Peak GPU: {max_gpu:.1f}°C</p>
</body></html>"""

    (report_artifacts / "thermal_profile.html").write_text(html)
    thermal.info("Thermal profile artifact saved", data={"file": "thermal_profile.html"})


# ---------------------------------------------------------------------------
# Parametrized sensor sweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sensor,max_temp",
    [
        ("cpu", 70.0),
        ("gpu", 75.0),
        ("vrm", 65.0),
        ("heatsink", 55.0),
    ],
    ids=["CPU", "GPU", "VRM", "Heatsink"],
)
def test_sensor_limits(log, verify, sensor, max_temp):
    """Verify each thermal sensor is within its rated limit."""
    thermal = log.child("thermal")

    temp = _read_temperature(sensor)

    with step(f"Read {sensor} sensor"):
        thermal.info(f"{sensor} temperature", data={"temp_c": temp})

    step(f"{sensor} below {max_temp} °C",
         check=verify.less(temp, max_temp, name=f"{sensor} temp", units="°C"))


# ---------------------------------------------------------------------------
# Skip and xfail
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Liquid cooling loop not installed in this test fixture")
def test_liquid_cooling_flow_rate(log, verify):
    """Verify coolant flow rate through the liquid cooling loop."""
    log.info("This should not execute")


@pytest.mark.xfail(reason="VRM thermal pad needs replacement -- known issue #THERM-445")
def test_vrm_thermal_throttling(log, verify, testbench):
    """VRM should not throttle below 100 W load -- expected fail with degraded pad."""
    thermal = log.child("thermal")

    with step("Apply 100 W CPU load"):
        thermal.info("Stress test started")

    vrm_temp = _read_temperature("vrm") + 25.0  # Simulate degraded pad

    with step("Check VRM temperature"):
        thermal.info("VRM temp", data={"temp_c": vrm_temp})

    step("VRM below 60 °C",
         check=verify.less(vrm_temp, 60.0, name="VRM under load", units="°C"))

    assert vrm_temp < 60.0, f"VRM at {vrm_temp}°C exceeds 60°C limit"


# ---------------------------------------------------------------------------
# Deliberate failure
# ---------------------------------------------------------------------------


def test_ambient_temperature_range(log, verify):
    """Ambient temp must be 20-25 °C per lab spec -- deliberate failure."""
    thermal = log.child("thermal")

    ambient = _read_temperature("ambient") + 5.0  # Push above range

    with step("Read lab ambient"):
        thermal.info("Ambient reading", data={"temp_c": ambient})

    step("Ambient in [20, 25] °C",
         check=verify.between(ambient, 20.0, 25.0, name="Lab ambient", units="°C"))
