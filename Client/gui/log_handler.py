"""
AlderSync Client - GUI Log Handler Module

Implements logging for GUI mode with custom handler and utilities.

Author: AlderSync Project
"""

import tkinter as tk
import logging
import sys
from pathlib import Path
from datetime import datetime

from managers import ConfigManager


class GUILogHandler(logging.Handler):
    """
    Custom logging handler that writes to GUI log panel.

    This handler is thread-safe and uses tkinter's after() method
    to safely update the GUI from any thread.
    """

    def __init__(self, log_widget, root_widget):
        """
        Initialize the GUI log handler.

        Args:
            log_widget: The scrolledtext widget to write logs to
            root_widget: The root tkinter window for thread-safe updates
        """
        super().__init__()
        self.log_widget = log_widget
        self.root_widget = root_widget

    def emit(self, record):
        """
        Emit a log record to the GUI log panel.

        Args:
            record: LogRecord to emit
        """
        try:
            msg = self.format(record)
            # Use after() for thread-safe GUI update
            self.root_widget.after(0, lambda: self._append_log(msg))
        except Exception:
            self.handleError(record)

    def _append_log(self, message: str):
        """
        Append message to log widget.

        Args:
            message: Formatted log message
        """
        try:
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)  # Auto-scroll to bottom
            self.log_widget.config(state=tk.DISABLED)
        except Exception:
            pass  # Widget may be destroyed


def setup_gui_logging(config_manager: ConfigManager, log_widget, root_widget) -> Path:
    """
    Setup logging for GUI mode with both file and GUI panel output.

    Creates log file with format: aldersync-gui-YYYY-MM-DD-HH-MM-SS.log
    in a "logs" subdirectory next to the executable or in the current directory.

    Args:
        config_manager: ConfigManager instance for log settings
        log_widget: The scrolledtext widget for GUI logging
        root_widget: The root tkinter window

    Returns:
        Path to the created log file
    """
    # Get log level from config
    log_level = config_manager.get("log_level", "INFO")

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    log_filename = f"aldersync-gui-{timestamp}.log"

    # Place log file in logs subdirectory
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = Path(sys.executable).parent
    else:
        # Running as script
        base_dir = Path.cwd()

    # Create logs subdirectory if it doesn't exist
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / log_filename

    # Configure logging with multiple handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Create formatter with timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # GUI handler
    gui_handler = GUILogHandler(log_widget, root_widget)
    gui_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    gui_handler.setFormatter(formatter)
    root_logger.addHandler(gui_handler)

    # Initial log message
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info(f"AlderSync GUI Mode - Log file: {log_file}")
    logger.info(f"Log level: {log_level}")
    logger.info("=" * 60)

    return log_file


def cleanup_old_logs(config_manager: ConfigManager, current_log: Path):
    """
    Delete log files older than retention period.

    Args:
        config_manager: ConfigManager instance for retention settings
        current_log: Path to current log file (don't delete this)
    """
    logger = logging.getLogger(__name__)
    retention_days = config_manager.get("log_retention_days", 30)

    if retention_days <= 0:
        return  # Retention disabled

    logger.info(f"Cleaning up log files older than {retention_days} days")

    log_dir = current_log.parent
    cutoff_time = datetime.now().timestamp() - (retention_days * 86400)

    deleted_count = 0
    # Clean up both GUI and CLI log files
    for pattern in ["aldersync-gui-*.log", "aldersync-*.log"]:
        for log_file in log_dir.glob(pattern):
            if log_file == current_log:
                continue  # Don't delete current log

            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete old log file {log_file}: {e}")

    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} old log file(s)")
