# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A check whose expected value comes from a variable shows the variable and this run's
  value on the Procedure tab: `Verify 'Readback' == <wdata> (243)` instead of `== 243`, so
  the line reads like stepdoc's procedure and still says what was compared. Checks with
  literal expected values are unchanged.

- Step titles with Markdown code spans (stepdoc's `` `backticks` `` or `fmt.mono(...)`) show
  those parts in monospace on the Procedure tab. `procedure.json` keeps the title in
  `description` and adds `description_segments` for such steps.

- The Procedure sub-tab shows the procedure in **Setup**, **Call** and **Teardown** tabs,
  like the phase logs: each tab shows its worst outcome and how many steps it has, and the
  tab opens on the phase that failed (else on Call). Retry attempts use the same tabs, and
  printing shows all three.

- The HTML report's Summary tab lists every failed run, with the line that says why it
  failed (the pytest-verifier summary or the traceback's first `E` line), a link to the run,
  and a **Copy rerun command** button that copies `pytest "<nodeid>" …` for all of them.
- A failed run starts with a strip that names the phase that failed and why, lists its
  failed checks, and links to the traceback and the Checks tab.
- The Summary counter cards open the Tests tab filtered to that status (Retried shows
  the retried tests, with a chip to clear it).
- The HTML report has a light theme. It follows the operating system's setting, and a
  button in the header switches between light and dark (the choice is remembered in the
  browser). Printing uses the light colours, hides the navigation and the test tree, and
  opens up scrolled log and traceback areas.

### Changed

- A test opens on its first failed run instead of run 01, and a run's phase logs open
  on the phase that failed (or was skipped) instead of Setup.
- When the run has failures, the Tests tab starts on them: only failed tests shown,
  their folders expanded, the first one open.
- Search and the status filters now apply together, and folders with nothing left to
  show are hidden. The status filter buttons expose `aria-pressed`.
- HTML report colours are all design tokens: status tints are mixed from the status
  colours, and the charts, header, overlays and log tables use tokens instead of fixed
  values. The status (graph) colours themselves are unchanged.
- HTML report type follows a seven-step scale (11, 12, 13, 15, 18, 24 and 36px) set as
  tokens, instead of thirteen sizes from 9 to 48px. Nothing is smaller than 11px: tree
  badges, counts, filter buttons and uppercase labels were 9–10px. Weights are 400–700,
  numbers use tabular figures, headings balance their lines, and long test names wrap
  only where they would overflow.
- On phones the report header keeps the title and the result badge on one line; the date
  and duration stay on the Report tab.
- On phones (up to 768px wide) the Tests tab shows the test list or one test at a time:
  picking a test opens it, and **All tests** goes back to the list on the same row. The
  tree used to take the top 45% of the screen above the test.
- On touch screens every control is at least 44px (tabs, tree rows, filters, run pills,
  phase tabs, buttons); with a mouse no control is under 24px (WCAG 2.5.8). The top tabs
  and the run sub-tabs scroll sideways instead of wrapping or clipping a tab, and phase
  tabs put the timing under the label when they are narrow.
- The HTML report opens faster: its data is a JSON block that the page reads with
  `JSON.parse` instead of a JavaScript object literal, written without padding spaces.
  In Chromium the example suite's report is interactive after 0.13s instead of 0.34s, and
  a 7 MB report (5,280 runs) after 0.9s instead of 1.8s with the CPU slowed 4×, using
  about half the memory. The data block escapes every `<`, so no logged text can end it.
- The sticky header and tab bar are solid instead of blurring what scrolls under them,
  which cost a repaint on every scroll frame, and buttons fade only their colours instead
  of every property.

### Fixed

- HTML report: secondary text and coloured status text now reach WCAG AA contrast (4.5:1)
  on every surface, in both themes. Grey labels, inactive tabs, times and file paths were
  2.7–3.5:1, and red badges about 4.1:1. Status text now uses a lighter shade of each status
  colour in the dark theme and a darker one in the light theme. The skip link is readable
  too (5.2:1).
- HTML report: the test tree works from the keyboard and with screen readers. Rows are a
  WAI-ARIA tree (`treeitem` with `aria-level`, `aria-expanded`, `aria-selected`), with one
  row in the Tab order; the arrow keys, Home and End move, Left and Right collapse and
  expand, Enter opens a test.
- HTML report: session-log sections, dashboard group bars and cards open with Enter or Space.
- HTML report: run sub-tabs and phase tabs are tablists with arrow-key navigation; run pills,
  status filters and log-level filters expose `aria-pressed`; run and test outcomes are read
  out as text, not only shown as colour; icon SVGs are hidden from screen readers.
- HTML report: the page has a skip link, `<header>` and `<main>` landmarks, tabs linked to
  their panels, and headings in order (no H1 → H3 jump).
- HTML report: HTML artifacts (`log.table()` tables) are sized from their row count instead
  of staying 200px tall, with a "Show all N rows" button past 13 rows and a frame title.
- HTML report: an empty-result message with "Show all tests" when search and filters
  match nothing; search results and copy confirmations are announced to screen readers.
- HTML report: the Tests tab no longer scrolls the page past the end of the panels into
  blank space. The test tree's screen-reader labels were positioned against the page,
  not the tree, so a long tree made the page as tall as the tree.
- HTML report: image artifacts open from the keyboard, and the image viewer is a dialog:
  focus moves to its close button and stays inside it, and Escape, the button or a click
  closes it and returns focus to the image.
- HTML report: a test with more than 20 runs no longer hides the run it opened on behind
  **Show more**; the button names how many runs and failures it holds ("Show 80 more
  (6 failed)") instead of "3p/1f/0s/0e", and the extra pills show their parameters like
  the first 20.
- HTML report: the search fields show the same 2px focus ring as every other control
  instead of a faint glow; cut-off test names in the tree show the full name on hover;
  searching the session logs opens the sections it matched.
- HTML report: wording and alignment details: "1 run" instead of "1 runs", "1 entry",
  child logger sections say "N entries" like their parents, the Total card says what it
  counts (runs) so the counter figures line up, and long values on the Report tab no
  longer touch their label on phones. On phones the pass rate and total time sit side by
  side.

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
