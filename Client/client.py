"""
AlderSync Client - Main Entry Point

This is the main entry point for the AlderSync client application.
Handles both GUI and CLI modes depending on command-line arguments.

Author: AlderSync Project
"""

import sys
import argparse


def main():
    """
    Main entry point for AlderSync client.

    Parses command-line arguments and launches either:
    - GUI mode (default when no arguments)
    - CLI mode (when operation specified: pull, push, reconcile)
    """
    parser = argparse.ArgumentParser(
        description='AlderSync - ProPresenter File Synchronization Client',
        epilog='Run without arguments to launch GUI mode'
    )

    # Optional positional argument for operation (pull, push, reconcile)
    parser.add_argument('operation', nargs='?', choices=['pull', 'push', 'reconcile'],
                       help='Operation to perform: pull, push, or reconcile (CLI mode)')

    # Optional service type override
    parser.add_argument('--service', choices=['Contemporary', 'Traditional'],
                       help='Service type (overrides config default)')

    args = parser.parse_args()

    # Determine mode based on arguments
    if args.operation:
        # CLI mode
        from cli import run_cli_operation
        exit_code = run_cli_operation(args.operation, args.service)
        return exit_code
    else:
        # GUI mode
        from gui import launch_gui
        launch_gui()
        return 0


if __name__ == '__main__':
    sys.exit(main())
