# test_summary.py
class TestResultTracker:
    def __init__(self):
        self.results = {}

    def add_result(self, test_name, outcome):
        if test_name not in self.results:
            self.results[test_name] = {'executions': 0, 'pass': 0, 'fail': 0, 'skip': 0, 'error': 0}

        self.results[test_name]['executions'] += 1
        if outcome == 'passed':
            self.results[test_name]['pass'] += 1
        elif outcome == 'failed':
            self.results[test_name]['fail'] += 1
        elif outcome == 'skipped':
            self.results[test_name]['skip'] += 1
        elif outcome == 'error':
            self.results[test_name]['error'] += 1

    def reset(self):
        """Reset all tracked results."""
        self.results = {}

    def has_results(self):
        """Check if any results have been tracked."""
        return bool(self.results)


class TestSummaryDisplay:
    def __init__(self, tracker: TestResultTracker):
        self.tracker = tracker

    def display_basic_table(self, terminalreporter):
        """Display a fancy results table using basic terminal formatting."""
        if not self.tracker.has_results():
            return
        
        # Calculate column widths
        max_test_name = max(len(name) for name in self.tracker.results.keys())
        test_col_width = max(max_test_name, len("Test Name")) + 2
        
        # Table formatting
        tw = terminalreporter._tw
        
        # Header
        tw.line("")
        tw.write("=" * 80, bold=True)
        tw.line("")
        tw.write(" TEST EXECUTION SUMMARY", bold=True, blue=True)
        tw.line("")
        tw.write("=" * 80, bold=True)
        tw.line("")
        
        # Column headers
        header = f"{'Test Name':<{test_col_width}} {'Executions':>11} {'PASS':>8} {'FAIL':>8} {'SKIP':>8} {'ERROR':>8}"
        tw.write(header, bold=True)
        tw.line("")
        tw.write("-" * 80)
        tw.line("")
        
        # Results rows
        for test_name, results in sorted(self.tracker.results.items()):
            executions = results['executions']
            passes = results['pass']
            failures = results['fail']
            skips = results['skip']
            errors = results['error']
            
            # Format row
            row = f"{test_name:<{test_col_width}} {executions:>11} "
            tw.write(row)
            
            # Colored pass count
            tw.write(f"{passes:>8}", green=True if passes > 0 else False)
            
            # Colored fail count  
            tw.write(f"{failures:>8}", red=True if failures > 0 else False)
            
            # Colored skip count
            tw.write(f"{skips:>8}", yellow=True if skips > 0 else False)
            
            # Colored error count
            tw.write(f"{errors:>8}", red=True if errors > 0 else False)
            
            tw.line("")
        
        tw.write("=" * 80, bold=True)
        tw.line("")

    def display_rich_table(self, terminalreporter):
        """Display results using Rich library for better formatting."""
        try:
            from rich.console import Console
            from rich.table import Table
            
            if not self.tracker.has_results():
                return
            
            console = Console()
            
            table = Table(title="🧪 Test Execution Summary\n", show_header=True, header_style="bold magenta")
            table.add_column("Test Name", style="cyan", no_wrap=True)
            table.add_column("Executions", justify="center", style="white")
            table.add_column("PASS", justify="center", style="green")
            table.add_column("FAIL", justify="center", style="red")
            table.add_column("SKIP", justify="center", style="yellow")
            table.add_column("ERROR", justify="center", style="bold red")
            
            for test_name, results in sorted(self.tracker.results.items()):
                table.add_row(
                    test_name,
                    str(results['executions']),
                    str(results['pass']),
                    str(results['fail']),
                    str(results['skip']),
                    str(results['error'])
                )
            
            # Print to terminal
            console.print(table)
            
        except ImportError:
            # Fallback to basic table if rich is not available
            self.display_basic_table(terminalreporter)

    def display_table(self, terminalreporter, use_rich=True):
        """Display the results table, preferring Rich if available."""
        print("\n")
        if use_rich:
            self.display_rich_table(terminalreporter)
        else:
            self.display_basic_table(terminalreporter)