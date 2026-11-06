# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0]

pytest-reporter no longer has a step API of its own: procedures come from
[stepdoc](https://github.com/guillegil/stepdoc). It also follows the renamed
pytest-verifier (0.10) and pytest-strategies 4.x. All three stay optional
extras; the reporter reads what they publish and never imports them.

### Added

- Procedures from stepdoc's `step()`: with stepdoc installed, the Procedure tab and
  `procedure.json` show each attempt's steps with timing and outcome, the actions
  stepdoc bridges record, and the checks made in each step (asserts, `step(check=...)`,
  pytest-verifier checks), with Setup (`S1`) and Teardown (`T1`) sections for steps
  run by fixtures. Nodes carry `kind` (`step`, `action`, `check`), `section`, `result`
  and `detail`.
- `stepdoc.json` in the run folder: stepdoc's run record, written when `--report-dir`
  is active and no `--stepdoc-*` option is given. The `report_stepdoc` ini setting
  (default `true`) turns this off.
- `checks.json` in each run and retry folder with that attempt's pytest-verifier checks;
  the Retries tab shows each attempt's checks.
- Verification cards show the check's result (`detail`), error, phase, where it was
  made, its `verify.section` titles (`3V3 › Vout`), `raises` fields, and the kept try
  of `eventually`/`stable`.
- pytest-strategies rows: the run Summary shows the strategy, row and seed, and
  `parameters.json` holds the row's `VectorInfo` under `strategy`.
- Optional extras `stepdoc`, `verifier`, `strategies` and `all`.
- An example combining the three integrations
  (`examples/tests/Hardware/Verification/test_dac_strategies.py`).

### Changed

- Verification checks are read from `report.verify_checks` (pytest-verifier 0.10)
  instead of `pytest_verify.get_check_results()`, so retry attempts keep their own
  checks.
- The seed in Run Information comes from the pytest-strategies rows that ran, instead of
  `RNG.get_seed()`: a session without strategy rows shows "Not Provided".
- The examples use `from stepdoc import step` and need the `[all]` extras.
- CI runs the tests with and without the optional integrations.

### Removed

- `pytest_reporter.step`, `substep`, `fmt`, `FormattedText`, `ProcedureError` and
  `ProcedureNestingError`. Importing them raises an `ImportError` that points to
  stepdoc; the README's "Moving from `pytest_reporter.step`" table shows the
  replacements.
- The `verify` extra and the warning about an outdated `pytest-verify`: the reporter
  no longer imports `pytest_verify`, a name that belongs to another project on PyPI.
