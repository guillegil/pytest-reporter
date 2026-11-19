# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Bench provenance: what was on the bench when the tests ran. The new session fixture
  `report_bench` and the new hook `pytest_reporter_bench(config, bench)` give a `BenchInfo`
  (exported for type hints) with `device(name, serial=, firmware=, hardware=, ...)`,
  `instrument(name, idn=, serial=, calibrated=, cal_due=, ...)`, `set(label, value,
  section="Bench")` and `update({...})`. A `*IDN?` reply of four parts also gives the
  manufacturer, model, serial and firmware. The data is written to `bench.json` in the run
  folder (before `junit.xml`, and also when the HTML report cannot be built), to `junit.xml`
  as properties of the test suite (`bench.<section>.<label>`, `bench.device.<name>.<key>`,
  `bench.instrument.<name>.<key>`), and to a **Bench** section in the Report tab. A wrong
  call raises `TypeError` or `ValueError` where it is made, also without `--report-dir`.
- An instrument whose `cal_due` is before the day of the run is marked overdue in the Bench
  section, named in a notice on the Summary tab and in one pytest warning at the end of the
  session (`pytest-reporter: instrument 'DMM' calibration was due 2026-03-02`). It never
  changes a test's outcome.
- A bench value changed after it was first given is kept as a change, with the time and the
  test (and retry attempt) that made it: a "Bench changed in this test" block in the test's
  Summary, `bench.changed` properties on its `<testcase>` in `junit.xml`, and a change history
  in the Bench section. A session, package, module or class fixture that pytest sets up again
  for a retry changes nothing when it gives the values it gave before.
- Bench values that are members of a `str` or `int` enum are stored as their plain value, so
  `bench.json`, `junit.xml` and the report read the same. A part of a `*IDN?` reply never
  replaces a value given by name, in the same call or an earlier one. `instrument(...,
  overdue=...)` raises `ValueError`: the report works that key out from `cal_due`.
- In the Instruments table a long value (an `*IDN?` reply, a firmware string) wraps inside its
  cell, and the calibration dates and the "overdue" badge never break, on screen and in print.
  The Summary notice's **Bench details** button shows the Bench section below the page's
  sticky header, outlined.
- `bench.json` and `junit.xml` also hold what `report_metadata` and
  `pytest_reporter_metadata()` gave (`metadata` in the file, `metadata.<section>.<label>`
  properties). The System Data panel shows them as before.
- Register checks of pytest-verifier 0.11 (`radix=`, `width=`, `verify.bits`, a value with
  `__verify_format__`). A card's Actual, Expected, Mask, Threshold, Low and High rows show the
  value as the check renders it, followed by the plain number (`0x12F0 (4848)`). A `bits`
  check, and a failed `equal` on integers, get a bit strip: one cell per bit, the expected row
  above the actual one, differing bits marked, bits outside the mask dimmed, one row per 32
  bits. A check with `fields` gets a table of each field's bits, actual and expected value.
  The strip scrolls inside the card on a phone, prints, and works with forced colours.
- The Procedure tab shows a check's value as stepdoc carries it (`actual_text`) and, for a
  failed check, how it differs (`difference`): `→ got 0x12F0, bits [1:0] differ: EN [0] is
  0b0, expected 0b1`. Items of a folded `all_satisfy` check show their rendered values
  (`each.texts`). A result too long for its line goes under it, and on a narrow page every
  check's result has its own line instead of squeezing the check's text.
- With warnings as errors (`-W error`), a `pytest_reporter_bench` or
  `pytest_reporter_metadata` implementation that raised is named in a `Warning:` line under
  `Report` in the terminal summary, where its warning could not be issued.

- A check made once per item (pytest-verifier's `all_satisfy`) is one line in the Procedure
  tab, not one line per item. With a stepdoc that folds these checks (`Check.each`) the line
  reads `Verify 'Index error clear': for each w in waveforms, w & INDEX_ERROR_BIT == 0` and
  its result says `12 of 12 passed` or `2 of 12 failed`. Only the items that failed are listed
  under it, each with its position and value (`Verify item [3]: w & INDEX_ERROR_BIT == 0 → got
  64`). A closed "Values of waveforms (12 items)" list under the line opens to show what every
  item's check got, the failed ones marked. The **Generic** view shows the line alone.
  `procedure.json` check nodes get `each` (`count`, `failed`, `failed_items`, `values`,
  `values_cut`, `item`, `items`). With an earlier stepdoc the items are listed as before.

- Custom HTML tabs in a test's detail. A `conftest.py` adds them for every test with the new
  `pytest_reporter_test_tabs(item, tabs)` hook, and a test or fixture adds its own with the
  new `report_tabs` fixture: `tabs.add("Bench log", html)`. The content is HTML as a string, the
  path of an HTML file, or an object with `_repr_html_()`. The tabs come after the report's own
  (Summary, Procedure, Checks, Strategy, Artifacts, Retries), each in a sandboxed frame that
  cannot read or change the report; JavaScript runs only with `scripts=True`. They are saved
  in the run folder (`tabs/`), per retry attempt. `ReportTabs` is exported for type hints.
- Checks made with pytest-verifier's `actual_name=` / `expected_name=` show those names.
  Verification cards, the failure strip and the Failures list show this run's text
  (`tb.dev.map.block.reg3.F`); a check that also has a `name=` keeps the name as its label
  and shows that text beside it. The card body has **Actual name** and **Expected name**
  rows, each followed by the form with the variable parts (`written as
  tb.dev.map.block.reg<channel>.F`) when pytest-verifier recorded one.
- The Procedure tab words such a check with the names as the test writes them, and names the
  value as this run has it in the result: `Verify tb.dev.map.block.reg<channel>.F == wdata
  (243) → got tb.dev.map.block.reg3.F = 240`. Check nodes in `procedure.json` have this
  run's names as `actual_name` and `expected_name`. Checks without operand names are
  unchanged.
- With pytest-strategies 4.3+, its run export (`strategies.json` and
  `strategies.vectors.json`) is saved in the run folder. The reporter answers
  pytest-strategies' `pytest_strategies_export_dir` hook with the run folder when no folder
  was chosen; a folder chosen with `--strategy-export`, another implementation of the hook
  or the `strategies_export_dir` ini option is kept, and the two files are copied into the
  run folder.
- The Procedure sub-tab has a **This run / Generic** switch. Generic shows the procedure as
  the test is written, with names in place of this run's values
  (`Verify tb.dev.map.block.reg<channel>.F == <wdata>`, `dev.reg<channel> = <wdata>`) and
  without results, outcomes or durations. `procedure.json` nodes carry the line as `generic`.
- Checked expressions and operand names on the Procedure tab are set in monospace (a
  check's `name=` stays plain text), and the report's monospace font stack starts with the
  system's own (`ui-monospace`, SF Mono, Menlo, Cascadia Mono, …).
- A test that uses a strategy has a **Strategy** sub-tab: where each strategy is defined,
  the `@strategy` arguments, the context fingerprint, the sample count and where it came
  from (a strategy with `pin_nsamples=True` is marked **pinned**), its arguments and
  constraints, and every row the test ran with its values and outcome. The row of the run
  on screen is highlighted and an outcome opens that run. Integers too large for a
  JavaScript number (64-bit register values) are shown exactly. The run's Summary shows the
  sample count, and the Report tab has a Strategies section (generator, seed, `--nsamples`
  and the number of tests, strategies and rows).
- The `report_strategies` ini setting (default `true`); `false` leaves pytest-strategies'
  export alone and hides the Strategy sub-tab.

- Loops that stepdoc collapses show as one entry on the Procedure tab: `Repeat until FIFO is
  empty → 16 times`, with one pass of the loop under it, instead of a line per pass.
  `procedure.json` has a new node kind, `repeat`. A write repeated from one line reads
  `Repeat dev.fifo.fifo_data = 90 → (16 times)` instead of `Poll … (16 calls)`. Needs a
  stepdoc version with loop collapsing; older ones are unchanged.
- A loop named with `stepdoc.repeat("Drain the FIFO", until="FIFO is empty")` is a step on
  the Procedure tab: `Drain the FIFO (repeat until FIFO is empty) → 16 times`, with one
  pass as its substeps. stepdoc's `counter=`/`inc=` show in the text
  (`…, counting write_count`, `write_count +4 each pass`).
- stepdoc's `note=` on a step or repeat shows in italics under its line on the Procedure
  tab, and as `note` in `procedure.json`.
- A check's note shows after its text on the Procedure tab, in parentheses, as in stepdoc:
  `Verify dev.block.esmi3_32dat.txfe == 1 (CMD FIFO empty)`. The note is pytest-verifier's
  `note=`, or the source comment that stepdoc found next to the check. Check nodes in
  `procedure.json` have it as `note`. Needs a stepdoc version with check notes; a comment
  note shows only when stepdoc fills it in before the test's `pytest_runtest_logfinish`.
- Verification cards show a check's `note` after its statement and in the card body, and
  in the failure banner. A name that pytest-verifier took from the source (`auto_name`,
  such as `dat.txfe`) shows in monospace.

- A check whose expected value comes from a variable shows the variable and this run's
  value on the Procedure tab: `Verify 'Readback' == <wdata> (243)` instead of `== 243`, so
  the line reads like stepdoc's procedure and still says what was compared. Checks with
  literal expected values are unchanged.

- A check that stepdoc words after the checked value (`dev.block.esmi<channel>_32dat.txfe ==
  1`, or `'FIFO not full': dev.block.esmi<channel>_ctl.tx == 0` when it has a name) shows that
  value as this run has it: `Verify dev.block.esmi3_32dat.txfe == 1`. Expected values given
  by name still show the name and the value, `wdata == <wdata> (243)`.

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

- The reporter's `pytest_runtest_teardown` is now a hook wrapper (it still asks for custom
  tabs before fixtures are torn down), so a bench change made while fixtures are torn down
  belongs to the test that was running.
- In the Procedure tab, a check whose expected value is written as a hex, binary or octal
  literal shows this run's value alone (`== 0x00F3`) instead of the literal followed by the
  same number in parentheses.
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

- An integer above 2**53 in a verification card (a 64-bit register, a large counter) lost its
  last digits, because the report read it as a JavaScript number. Such values now reach the
  report as text and show exactly.
- The test tree of the HTML report was empty when every test was in one file (or one
  class): the Tests tab said "No tests match the search and filters". The file is now the
  tree's top row.

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
