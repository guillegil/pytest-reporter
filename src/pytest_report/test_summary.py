# test_summary.py
import sys
import platform
import pytest
import re
import time


class TestResultTracker:
    def __init__(self):
        self.results = {}
        self.test_start_times = {}

    def _get_base_test_name(self, test_name):
        """Extract base test name without parameters."""
        # Remove parameters like [a=2,b=3,expected=5] from test names
        base_name = re.sub(r'\[.*?\]$', '', test_name)
        return base_name

    def start_test(self, test_name):
        """Record the start time of a test."""
        self.test_start_times[test_name] = time.time()

    def add_result(self, test_name, outcome, duration=None):
        # Group by base test name (without parameters)
        base_name = self._get_base_test_name(test_name)
        
        if base_name not in self.results:
            self.results[base_name] = {
                'executions': 0, 
                'pass': 0, 
                'fail': 0, 
                'skip': 0, 
                'error': 0,
                'total_duration': 0.0
            }

        self.results[base_name]['executions'] += 1
        
        # Add duration if provided, otherwise calculate from start time
        if duration is not None:
            self.results[base_name]['total_duration'] += duration
        elif test_name in self.test_start_times:
            test_duration = time.time() - self.test_start_times[test_name]
            self.results[base_name]['total_duration'] += test_duration
            del self.test_start_times[test_name]  # Clean up
        
        if outcome == 'passed':
            self.results[base_name]['pass'] += 1
        elif outcome == 'failed':
            self.results[base_name]['fail'] += 1
        elif outcome == 'skipped':
            self.results[base_name]['skip'] += 1
        elif outcome == 'error':
            self.results[base_name]['error'] += 1

    def reset(self):
        """Reset all tracked results."""
        self.results = {}
        self.test_start_times = {}

    def has_results(self):
        """Check if any results have been tracked."""
        return bool(self.results)

    def get_totals(self):
        """Get total counts across all tests."""
        totals = {'executions': 0, 'pass': 0, 'fail': 0, 'skip': 0, 'error': 0, 'total_duration': 0.0}
        for results in self.results.values():
            for key in totals:
                totals[key] += results[key]
        return totals

    def get_success_rate(self, test_results):
        """Calculate success rate for a test."""
        total = test_results['executions']
        if total == 0:
            return 0.0
        return (test_results['pass'] / total) * 100

    def get_overall_success_rate(self):
        """Calculate overall success rate."""
        totals = self.get_totals()
        if totals['executions'] == 0:
            return 0.0
        return (totals['pass'] / totals['executions']) * 100

    def format_duration(self, duration):
        """Format duration in a human-readable way with proper hours/minutes/seconds formatting."""
        if duration < 0.001:  # Less than 1ms
            return f"{duration*1000000:.0f}μs"
        elif duration < 1:  # Less than 1s
            return f"{duration*1000:.0f}ms"
        elif duration < 60:  # Less than 1 minute
            return f"{duration:.2f}s"
        elif duration < 3600:  # Less than 1 hour
            minutes = int(duration // 60)
            seconds = duration % 60
            return f"{minutes}m {seconds:.1f}s"
        elif duration < 86400:  # Less than 1 day
            hours = int(duration // 3600)
            remaining = duration % 3600
            minutes = int(remaining // 60)
            seconds = remaining % 60
            return f"{hours}h {minutes}m {seconds:.1f}s"
        else:  # 1 day or more
            days = int(duration // 86400)
            remaining = duration % 86400
            hours = int(remaining // 3600)
            remaining = remaining % 3600
            minutes = int(remaining // 60)
            seconds = remaining % 60
            return f"{days}d {hours}h {minutes}m {seconds:.1f}s"


class TestSessionInfo:
    def __init__(self):
        self.collected_tests = 0
        self.plugins = []
        self.config = None
        self.markers = []

    def set_session_data(self, config, items):
        """Set session information from pytest config and collected items."""
        self.config = config
        self.collected_tests = len(items) if items else 0
        self.plugins = self._get_active_plugins(config)
        self.markers = self._get_markers(config, items)

    def _get_active_plugins(self, config):
        """Get list of active pytest plugins."""
        if not config:
            return []
        
        plugins = []
        plugin_manager = config.pluginmanager
        
        # Get all loaded plugins
        for plugin in plugin_manager.list_plugin_distinfo():
            if plugin[1]:  # plugin[1] is the distribution info
                plugins.append(plugin[1].project_name)
        
        # Add built-in plugins that are always active
        builtin_plugins = ['cacheprovider', 'capture', 'doctest', 'junitxml', 'mark', 'pastebin', 
                          'pytester', 'python', 'recwarn', 'resultlog', 'skipping', 'terminal', 
                          'tmpdir', 'unittest', 'warnings']
        
        # Filter out some common built-ins and add custom ones
        filtered_plugins = [p for p in plugins if p not in ['pytest', 'pluggy']]
        
        return sorted(list(set(filtered_plugins + builtin_plugins)))

    def _get_markers(self, config, items):
        """Get list of markers used in the test session."""
        if not config or not items:
            return []
        
        markers = set()
        
        # Get markers from collected test items
        for item in items:
            if hasattr(item, 'iter_markers'):
                for marker in item.iter_markers():
                    markers.add(marker.name)
        
        # Get registered markers from config
        if hasattr(config, '_markers') and config._markers:
            for marker_name in config._markers:
                markers.add(marker_name)
        
        # Filter out built-in pytest markers that are less interesting
        builtin_markers = {'parametrize', 'skip', 'skipif', 'xfail', 'usefixtures', 'filterwarnings'}
        custom_markers = [m for m in markers if m not in builtin_markers]
        
        return sorted(custom_markers) if custom_markers else sorted(list(markers))

    def get_system_info(self):
        """Get system information."""
        return {
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'pytest_version': pytest.__version__,
            'platform': platform.system(),
            'platform_version': platform.release(),
            'architecture': platform.machine()
        }


class TestSummaryDisplay:
    def __init__(self, tracker: TestResultTracker, session_info: TestSessionInfo):
        self.tracker = tracker
        self.session_info = session_info

    def _get_terminal_width(self, terminalreporter):
        """Get terminal width, with fallback."""
        try:
            if hasattr(terminalreporter, '_tw') and hasattr(terminalreporter._tw, 'fullwidth'):
                return terminalreporter._tw.fullwidth
            elif hasattr(terminalreporter, 'get_terminal_width'):
                return terminalreporter.get_terminal_width()
            else:
                # Try to get from shutil
                import shutil
                return shutil.get_terminal_size().columns
        except:
            return 80  # Fallback to 80 columns

    def _calculate_table_dimensions(self, terminalreporter):
        """Calculate optimal table dimensions based on terminal width."""
        terminal_width = self._get_terminal_width(terminalreporter)
        
        # Reserve space for borders and padding
        # Format: │ St │ Test Name │ Exec │ PASS │ FAIL │ SKIP │ ERR │ Rate │
        # Borders: 2 + 3 + 3 + 3 + 3 + 3 + 3 + 3 + 2 = 25 chars for borders/spaces
        fixed_cols_width = 2 + 6 + 6 + 6 + 6 + 5 + 7  # St + Exec + PASS + FAIL + SKIP + ERR + Rate
        borders_padding = 25
        
        available_for_test_name = terminal_width - fixed_cols_width - borders_padding
        
        # Ensure minimum and maximum widths for test name
        min_test_name_width = 15
        max_test_name_width = 50
        
        test_name_width = max(min_test_name_width, min(available_for_test_name, max_test_name_width))
        
        # Calculate total table width
        total_width = test_name_width + fixed_cols_width + borders_padding
        
        # Ensure we don't exceed terminal width
        if total_width > terminal_width:
            total_width = terminal_width - 2
            test_name_width = total_width - fixed_cols_width - borders_padding
        
        return {
            'total_width': total_width,
            'test_name_width': test_name_width,
            'terminal_width': terminal_width
        }

    def _get_status_indicator(self, results):
        """Get status indicator based on test results."""
        if results['error'] > 0:
            return "❌", "red"
        elif results['fail'] > 0:
            return "❌", "red"
        elif results['skip'] > 0 and results['pass'] == 0:
            return "⏭️ ", "yellow"
        elif results['pass'] > 0 and (results['fail'] == 0 and results['error'] == 0):
            return "✅", "green"
        else:
            return "⚠️", "yellow"

    def _calculate_string_display_width(self, text):
        """Calculate the actual display width of a string, accounting for emojis and special characters."""
        # This is a simplified version - emojis typically take 2 display columns
        width = 0
        for char in text:
            if ord(char) > 0x1F000:  # Rough check for emojis
                width += 2
            else:
                width += 1
        return width

    def display_session_header(self, terminalreporter):
        """Display session information at the beginning."""
        tw = terminalreporter._tw
        system_info = self.session_info.get_system_info()
        terminal_width = self._get_terminal_width(terminalreporter)
        header_width = min(terminal_width - 2, 80)
        
        # Header
        tw.line("")
        tw.write("=" * header_width, bold=True)
        tw.line("")
        tw.write(" TEST SESSION INFORMATION", bold=True, cyan=True)
        tw.line("")
        tw.write("=" * header_width, bold=True)
        tw.line("")
        
        # System Information
        tw.write("System Information:", bold=True)
        tw.line("")
        tw.write(f"  OS: {system_info['platform']} {system_info['platform_version']} ({system_info['architecture']})")
        tw.line("")
        tw.write(f"  Python: {system_info['python_version']}")
        tw.line("")
        tw.write(f"  Pytest: {system_info['pytest_version']}")
        tw.line("")
        tw.line("")
        
        # Test Collection Information
        tw.write("Test Collection:", bold=True)
        tw.line("")
        tw.write(f"  Collected Tests: {self.session_info.collected_tests}", green=True if self.session_info.collected_tests > 0 else False)
        tw.line("")
        tw.line("")
        
        # Markers Information
        tw.write("Test Markers:", bold=True)
        tw.line("")
        if self.session_info.markers:
            # Calculate markers per row based on terminal width
            avg_marker_length = sum(len(m) for m in self.session_info.markers) / len(self.session_info.markers)
            markers_per_row = max(1, int((terminal_width - 4) / (avg_marker_length + 3)))
            
            for i in range(0, len(self.session_info.markers), markers_per_row):
                row_markers = self.session_info.markers[i:i+markers_per_row]
                marker_row = "  " + " | ".join(f"@{marker}" for marker in row_markers)
                # tw.write(marker_row, magenta=True)
                tw.write(marker_row)
                tw.line("")
        else:
            tw.write("  No custom markers detected", yellow=True)
            tw.line("")
        
        tw.line("")
        
        # Active Plugins
        tw.write("Active Plugins:", bold=True)
        tw.line("")
        if self.session_info.plugins:
            # Calculate plugins per row based on terminal width
            avg_plugin_length = sum(len(p) for p in self.session_info.plugins) / len(self.session_info.plugins)
            plugins_per_row = max(1, int((terminal_width - 4) / (avg_plugin_length + 3)))
            
            for i in range(0, len(self.session_info.plugins), plugins_per_row):
                row_plugins = self.session_info.plugins[i:i+plugins_per_row]
                plugin_row = "  " + " | ".join(plugin for plugin in row_plugins)
                tw.write(plugin_row, blue=True)
                tw.line("")
        else:
            tw.write("  No plugins detected")
            tw.line("")
        
        tw.line("")
        tw.write("=" * header_width, bold=True)
        tw.line("")

    def display_basic_table(self, terminalreporter):
        """Display a fancy results table using basic terminal formatting with enhanced panels style."""
        if not self.tracker.has_results():
            return
        
        tw = terminalreporter._tw
        totals = self.tracker.get_totals()
        overall_success_rate = self.tracker.get_overall_success_rate()
        
        # Calculate dimensions
        dimensions = self._calculate_table_dimensions(terminalreporter)
        terminal_width = dimensions['terminal_width']
        # Use a safe width that accounts for terminal limitations
        total_width = min(terminal_width - 2, 100)  # Leave margin for safety
        inner_width = total_width - 2  # Account for outer borders
        
        # Main Header
        tw.line("")
        tw.write("=" * total_width, bold=True)
        tw.line("")
        header_text = " TEST EXECUTION SUMMARY"
        padding = (total_width - len(header_text)) // 2
        tw.write(" " * padding + header_text, bold=True, blue=True)
        tw.line("")
        tw.write("=" * total_width, bold=True)
        tw.line("")
        
        # Summary Statistics Panel
        tw.write("┌" + "─" * inner_width + "┐", cyan=True)
        tw.line("")
        
        # Stats title line
        stats_title = " 📊 EXECUTION STATISTICS"
        tw.write("│", cyan=True)
        tw.write(stats_title.ljust(inner_width), bold=True, cyan=True)
        tw.write("│", cyan=True)
        tw.line("")
        
        tw.write("├" + "─" * inner_width + "┤", cyan=True)
        tw.line("")
        
        # Statistics content with total time
        total_time_str = self.tracker.format_duration(totals['total_duration'])
        
        # Build the stats content piece by piece to ensure proper alignment
        tw.write("│ ", cyan=True)
        
        # Calculate the actual content that will be displayed
        stats_parts = []
        stats_parts.append(f"Total: {totals['executions']}")
        stats_parts.append(f"PASSED: {totals['pass']}")
        stats_parts.append(f"FAILED: {totals['fail']}")
        stats_parts.append(f"TIME: {total_time_str}")
        stats_parts.append(f"SUCCESS: {overall_success_rate:.1f}%")
        
        # Join with separators
        stats_content = " │ ".join(stats_parts)
        
        # Check if content fits
        if len(stats_content) <= inner_width - 2:
            # Display full stats
            tw.write("Total: ", cyan=True)
            tw.write(f"{totals['executions']}", bold=True)
            tw.write(" │ PASSED: ", cyan=True)
            tw.write(f"{totals['pass']}", green=True if totals['pass'] > 0 else False)
            tw.write(" │ FAILED: ", cyan=True)
            tw.write(f"{totals['fail']}", red=True if totals['fail'] > 0 else False)
            tw.write(" │ TIME: ", cyan=True)
            tw.write(f"{total_time_str}", bold=True)
            tw.write(" │ SUCCESS: ", cyan=True)
            
            if overall_success_rate >= 80:
                tw.write(f"{overall_success_rate:.1f}%", green=True)
            elif overall_success_rate >= 60:
                tw.write(f"{overall_success_rate:.1f}%", yellow=True)
            else:
                tw.write(f"{overall_success_rate:.1f}%", red=True)
            
            # Fill remaining space
            remaining = inner_width - len(stats_content) - 2
            tw.write(" " * remaining)
        else:
            # Compact display
            compact_stats = f"T:{totals['executions']} P:{totals['pass']} F:{totals['fail']} {overall_success_rate:.1f}%"
            tw.write(compact_stats)
            remaining = inner_width - len(compact_stats) - 2
            tw.write(" " * remaining)
        
        tw.write(" │", cyan=True)
        tw.line("")
        
        tw.write("└" + "─" * inner_width + "┘", cyan=True)
        tw.line("")
        tw.line("")
        
        # Performance Dashboard
        self.display_basic_performance_dashboard(terminalreporter)

    def display_basic_performance_dashboard(self, terminalreporter):
        """Display simplified performance dashboard using basic terminal formatting."""
        if not self.tracker.has_results():
            return
        
        tw = terminalreporter._tw
        terminal_width = self._get_terminal_width(terminalreporter)
        # Use a safe width
        panel_width = min(terminal_width - 2, 100)
        inner_width = panel_width - 2
        
        # Calculate total time for title
        totals = self.tracker.get_totals()
        total_time_str = self.tracker.format_duration(totals['total_duration'])
        
        # Performance Dashboard Panel
        tw.write("┌" + "─" * inner_width + "┐", blue=True)
        tw.line("")
        
        # Dashboard title
        dashboard_title = f" 📊 TEST PERFORMANCE DASHBOARD - 🕐 {total_time_str}"
        tw.write("│", blue=True)
        # Truncate title if too long
        if len(dashboard_title) > inner_width:
            dashboard_title = dashboard_title[:inner_width-3] + "..."
        tw.write(dashboard_title.ljust(inner_width), bold=True, blue=True)
        tw.write("│", blue=True)
        tw.line("")
        
        tw.write("├" + "─" * inner_width + "┤", blue=True)
        tw.line("")
        
        for test_name, results in sorted(self.tracker.results.items()):
            success_rate = self.tracker.get_success_rate(results)
            status_icon, _ = self._get_status_indicator(results)
            duration_str = self.tracker.format_duration(results['total_duration'])
            
            # Create visual progress bar
            bar_length = min(25, inner_width // 3)  # Adjust bar length based on available space
            filled_length = int(bar_length * success_rate / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            
            # Test name line with time
            tw.write("│ ", blue=True)
            
            # Build the test line content
            test_line_parts = []
            test_line_parts.append(f"{status_icon} {test_name}")
            test_line_parts.append(f"🕐 {duration_str}")
            test_line_content = "  -  ".join(test_line_parts)
            
            # Truncate if necessary
            max_test_line_length = inner_width - 2
            if len(test_line_content) > max_test_line_length:
                # Truncate the test name part
                max_name_length = max_test_line_length - len(f"  -  🕐 {duration_str}") - 5
                truncated_name = test_name[:max_name_length] + "..."
                test_line_content = f"{status_icon} {truncated_name}  -  🕐 {duration_str}"
            
            # Write test line
            tw.write(f"{status_icon} {test_name}", cyan=True, bold=True)
            tw.write("  -  ", blue=True)
            tw.write("🕐 ", yellow=True)
            tw.write(f"{duration_str}", bold=True, yellow=True)
            
            # Calculate and fill remaining space
            display_width = self._calculate_string_display_width(test_line_content)
            remaining_space = inner_width - display_width
            tw.write(" " * max(0, remaining_space))
            tw.write("│", blue=True)
            tw.line("")
            
            # Progress bar line
            tw.write("│    Success Rate: ", blue=True)
            tw.write(f"{success_rate:>6.1f}% ", bold=True)
            
            if success_rate >= 80:
                tw.write(f"[{bar}]", green=True)
            elif success_rate >= 60:
                tw.write(f"[{bar}]", yellow=True)
            else:
                tw.write(f"[{bar}]", red=True)
            
            tw.write(f" ({results['pass']}/{results['executions']})")
            
            # Calculate remaining space for progress line
            progress_content = f"    Success Rate: {success_rate:>6.1f}% [{bar}] ({results['pass']}/{results['executions']})"
            progress_display_width = self._calculate_string_display_width(progress_content)
            remaining_space = inner_width - progress_display_width
            tw.write(" " * max(0, remaining_space))
            tw.write("│", blue=True)
            tw.line("")
            
            # Add separator line between tests
            tw.write("│" + " " * inner_width + "│", blue=True)
            tw.line("")
        
        tw.write("└" + "─" * inner_width + "┘", blue=True)
        tw.line("")

    def display_rich_header(self, terminalreporter):
        """Display session header using Rich library."""
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.columns import Columns
            from rich.text import Text
            
            # Get terminal width for Rich console
            terminal_width = self._get_terminal_width(terminalreporter)
            console = Console(width=terminal_width)
            system_info = self.session_info.get_system_info()
            
            # System Information Panel
            system_text = Text()
            system_text.append(f"OS: {system_info['platform']} {system_info['platform_version']} ({system_info['architecture']})\n", style="white")
            system_text.append(f"Python: {system_info['python_version']}\n", style="green")
            system_text.append(f"Pytest: {system_info['pytest_version']}", style="blue")
            
            system_panel = Panel(system_text, title="🖥️  System Information", border_style="cyan", expand=False)
            
            # Test Collection Panel
            collection_text = Text()
            collection_text.append(f"Collected Tests: {self.session_info.collected_tests}", 
                                 style="green bold" if self.session_info.collected_tests > 0 else "red")
            
            collection_panel = Panel(collection_text, title="📊 Test Collection", border_style="green", expand=False)
            
            # Markers Panel
            markers_text = Text()
            if self.session_info.markers:
                # Adapt markers per line based on terminal width
                avg_marker_length = sum(len(m) for m in self.session_info.markers) / len(self.session_info.markers)
                markers_per_line = max(1, int((terminal_width - 10) / (avg_marker_length + 5)))
                
                lines = []
                for i in range(0, len(self.session_info.markers), markers_per_line):
                    line_markers = self.session_info.markers[i:i+markers_per_line]
                    lines.append(" | ".join(f"@{marker}" for marker in line_markers))
                
                markers_text.append("\n".join(lines), style="magenta bold")
            else:
                markers_text.append("No custom markers detected", style="yellow")
            
            markers_panel = Panel(markers_text, title="🔖 Test Markers", border_style="magenta", expand=False)
            
            # Plugins Panel
            plugins_text = Text()
            if self.session_info.plugins:
                # Adapt plugins per line based on terminal width
                avg_plugin_length = sum(len(p) for p in self.session_info.plugins) / len(self.session_info.plugins)
                plugins_per_line = max(1, int((terminal_width - 10) / (avg_plugin_length + 5)))
                
                lines = []
                for i in range(0, len(self.session_info.plugins), plugins_per_line):
                    line_plugins = self.session_info.plugins[i:i+plugins_per_line]
                    lines.append(" | ".join(line_plugins))
                
                plugins_text.append("\n".join(lines), style="blue")
            else:
                plugins_text.append("No plugins detected", style="yellow")
            
            plugins_panel = Panel(plugins_text, title="🔌 Active Plugins", border_style="blue", expand=False)
            
            # Display panels
            console.print("\n")
            console.print(Panel.fit("🧪 TEST SESSION INFORMATION", style="bold magenta"))
            
            # Adapt layout based on terminal width
            if terminal_width >= 120:
                console.print(Columns([system_panel, collection_panel], equal=True, expand=False))
                console.print(markers_panel)
            else:
                console.print(system_panel)
                console.print(collection_panel)
                console.print(markers_panel)
            
            console.print(plugins_panel)
            console.print("\n")
            
        except ImportError:
            # Fallback to basic header if rich is not available
            self.display_session_header(terminalreporter)

    def display_performance_dashboard(self, terminalreporter):
        """Display simplified performance dashboard using Rich library."""
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            
            if not self.tracker.has_results():
                return
            
            terminal_width = self._get_terminal_width(terminalreporter)
            console = Console(width=terminal_width)
            totals = self.tracker.get_totals()
            overall_success_rate = self.tracker.get_overall_success_rate()
            total_time_str = self.tracker.format_duration(totals['total_duration'])
            
            # Enhanced Statistics Panel
            stats_text = Text()
            stats_text.append(f"Total Executions: {totals['executions']}\n", style="bold white")
            stats_text.append(f"✅ PASSED: {totals['pass']}\n", style="bold green")
            stats_text.append(f"❌ FAILED: {totals['fail']}\n", style="bold red")
            stats_text.append(f"⏭️  SKIPPED: {totals['skip']}\n", style="bold yellow")
            stats_text.append(f"💥 ERRORS: {totals['error']}\n", style="bold red")
            stats_text.append(f"🕐 TOTAL TIME: {total_time_str}\n", style="bold yellow")
            stats_text.append(f"📈 SUCCESS RATE: {overall_success_rate:.1f}%", 
                            style="bold green" if overall_success_rate >= 80 else 
                                ("bold yellow" if overall_success_rate >= 60 else "bold red"))
            
            stats_panel = Panel(stats_text, title="📊 Execution Statistics", border_style="cyan", expand=False)
            
            # Simplified Performance Dashboard with total time in title
            dashboard_text = Text()
            dashboard_text.append("\n")
            
            for test_name, results in sorted(self.tracker.results.items()):
                success_rate = self.tracker.get_success_rate(results)
                status_icon, _ = self._get_status_indicator(results)
                duration_str = self.tracker.format_duration(results['total_duration'])
                
                # Create a visual bar for success rate
                bar_length = 25
                filled_length = int(bar_length * success_rate / 100)
                bar = "█" * filled_length + "░" * (bar_length - filled_length)
                
                dashboard_text.append(f"{status_icon} {test_name}", style="cyan bold")
                dashboard_text.append("  -  ", style="blue")
                dashboard_text.append("🕐 ", style="yellow")
                dashboard_text.append(f"{duration_str}\n", style="bold yellow")
                dashboard_text.append(f"   Success Rate: {success_rate:>6.1f}% ", style="white")
                
                if success_rate >= 80:
                    dashboard_text.append(f"[{bar}]", style="green")
                elif success_rate >= 60:
                    dashboard_text.append(f"[{bar}]", style="yellow")
                else:
                    dashboard_text.append(f"[{bar}]", style="red")
                    
                dashboard_text.append(f" ({results['pass']}/{results['executions']})\n\n", style="dim white")
            
            dashboard_panel = Panel(dashboard_text, title=f"📊 Test Performance Dashboard - 🕐 {total_time_str}", border_style="blue", expand=False)
            
            # Display everything
            console.print("\n")
            console.print(Panel.fit("🧪 TEST EXECUTION SUMMARY", style="bold blue"))
            console.print(stats_panel)
            console.print(dashboard_panel)
            console.print("\n")
            
        except ImportError:
            # Fallback to basic dashboard if rich is not available
            self.display_basic_table(terminalreporter)

    def display_header(self, terminalreporter, use_rich=True):
        """Display the session header, preferring Rich if available."""
        if use_rich:
            self.display_rich_header(terminalreporter)
        else:
            self.display_session_header(terminalreporter)

    def display_table(self, terminalreporter, use_rich=True):
        """Display the results dashboard, preferring Rich if available."""
        if use_rich:
            self.display_performance_dashboard(terminalreporter)
        else:
            self.display_basic_table(terminalreporter)