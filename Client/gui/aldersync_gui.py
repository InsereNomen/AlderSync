"""
AlderSync Client - Main GUI Module

Implements the main AlderSyncGUI class and launch function.

Author: AlderSync Project
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import os
import sys
from typing import Optional

from managers import ConfigManager, FolderManager
from models import FolderValidationState, get_validation_error_message
from api import AlderSyncAPI
from exceptions import AlderSyncAuthError, AlderSyncServerError
from operations import SyncOperations
from updater import ClientUpdater
from version import VERSION
from .log_handler import setup_gui_logging, cleanup_old_logs
from .settings_dialog import SettingsDialog
from .revision_history_dialog import RevisionHistoryDialog


class AlderSyncGUI:
    """
    Main GUI window for AlderSync client.

    Layout includes:
    - Current service indicator (prominent display)
    - Operation buttons (Pull, Push, Reconcile, Swap)
    - Status bar at bottom
    - Toggleable log panel
    - Menu bar with Settings option
    """

    def __init__(self):
        """Initialize the GUI window and components."""
        self.root = tk.Tk()
        self.root.title("AlderSync - ProPresenter File Sync")

        # Hide window during initialization to avoid flicker
        self.root.withdraw()

        # Set Windows taskbar icon (must be done before creating window on Windows)
        if sys.platform == 'win32':
            try:
                import ctypes
                # Set app ID so Windows taskbar shows our icon instead of python.exe icon
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('aldersync.client.gui')
            except Exception:
                pass  # Ignore errors on systems where this isn't supported

        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'aldersync_icon.ico')
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Set window size and minimum size
        window_width = 700
        window_height = 400
        self.root.minsize(600, 300)

        # Set initial size without position
        self.root.geometry(f"{window_width}x{window_height}")

        # Initialize state
        self.current_service = "Unknown"  # Will be updated when authentication succeeds
        self.log_panel_visible = False
        self.config_mgr = ConfigManager()
        self.api = None
        self.folder_mgr = None  # Will be initialized after config is loaded
        self.sync_ops = None  # Will be initialized after API and folder manager are ready
        self.operation_in_progress = False
        self.last_operation_message = ""  # Track last progress message for admin cancellation detection

        # Build GUI components
        self.create_menu_bar()
        self.create_service_indicator()
        self.create_operation_buttons()
        self.create_log_panel()
        self.create_status_bar()

        # Setup logging after log panel is created
        self.config_mgr.load_config()
        self.log_file = setup_gui_logging(self.config_mgr, self.log_text, self.root)
        cleanup_old_logs(self.config_mgr, self.log_file)

        # Initially disable operation buttons (will be enabled after login)
        self.disable_operations()

        # Center window on screen after all components are built
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"+{x}+{y}")

        # Show the window now that it's properly positioned
        self.root.deiconify()

        # Perform startup login flow
        self.root.after(100, self.startup_login)

    def create_menu_bar(self):
        """Create the menu bar with Settings option."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Log Panel", command=self.toggle_log_panel)
        view_menu.add_separator()
        view_menu.add_command(label="Revision History", command=self.show_revision_history)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_service_indicator(self):
        """Create the prominent current service indicator."""
        # Frame for service indicator
        service_frame = tk.Frame(self.root, bg="#2c3e50", pady=15)
        service_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Service label
        label = tk.Label(service_frame, text="Current Service:",
                        font=("Arial", 11), bg="#2c3e50", fg="white")
        label.pack()

        # Service indicator (large, prominent)
        self.service_label = tk.Label(service_frame, text=self.current_service,
                                     font=("Arial", 20, "bold"), bg="#2c3e50", fg="#3498db")
        self.service_label.pack()

    def create_operation_buttons(self):
        """Create the operation buttons (Pull, Push, Reconcile, Swap)."""
        # Frame for buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure grid to expand
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.rowconfigure(0, weight=1)
        button_frame.rowconfigure(1, weight=1)

        # Button style configuration
        button_config = {
            "font": ("Arial", 12),
            "width": 15,
            "height": 2
        }

        # Pull button
        self.pull_button = tk.Button(button_frame, text="Pull",
                                     command=self.on_pull, **button_config)
        self.pull_button.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Push button
        self.push_button = tk.Button(button_frame, text="Push",
                                     command=self.on_push, **button_config)
        self.push_button.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # Reconcile button
        self.reconcile_button = tk.Button(button_frame, text="Reconcile",
                                         command=self.on_reconcile, **button_config)
        self.reconcile_button.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # Swap button
        self.swap_button = tk.Button(button_frame, text="Swap Service",
                                    command=self.on_swap, **button_config)
        self.swap_button.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

    def create_log_panel(self):
        """Create the toggleable log panel (hidden by default)."""
        # Frame for log panel
        self.log_frame = tk.Frame(self.root)
        # Not packed initially - will be packed when toggled

        # Log label
        log_label = tk.Label(self.log_frame, text="Operation Log:",
                            font=("Arial", 10, "bold"))
        log_label.pack(anchor=tk.W, padx=5, pady=(5, 0))

        # Scrolled text widget for log output
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10,
                                                  font=("Courier", 9),
                                                  wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_status_bar(self):
        """Create the status bar at the bottom."""
        # Status bar frame
        status_frame = tk.Frame(self.root, bd=1, relief=tk.SUNKEN)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Status label
        self.status_label = tk.Label(status_frame, text="Ready",
                                     font=("Arial", 9), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=2)

    def update_service_indicator(self, service_type: str):
        """
        Update the current service indicator.

        Args:
            service_type: Service type ("Contemporary" or "Traditional")
        """
        self.current_service = service_type
        self.service_label.config(text=service_type)

    def update_status_bar(self, message: str):
        """
        Update the status bar with a new message.

        Args:
            message: Status message to display
        """
        self.status_label.config(text=message)
        # Force immediate GUI update so status changes are visible before blocking operations
        self.root.update_idletasks()

    def log_message(self, message: str):
        """
        Add a message to the log panel.

        Args:
            message: Log message to add
        """
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # Auto-scroll to bottom
        self.log_text.config(state=tk.DISABLED)

    def toggle_log_panel(self):
        """Toggle the visibility of the log panel."""
        if self.log_panel_visible:
            # Hide log panel
            self.log_frame.pack_forget()
            self.log_panel_visible = False
        else:
            # Show log panel (insert before status bar)
            self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
            self.log_panel_visible = True

    def enable_operations(self):
        """Enable all operation buttons."""
        self.pull_button.config(state=tk.NORMAL)
        self.push_button.config(state=tk.NORMAL)
        self.reconcile_button.config(state=tk.NORMAL)
        self.swap_button.config(state=tk.NORMAL)

    def disable_operations(self):
        """Disable all operation buttons."""
        self.pull_button.config(state=tk.DISABLED)
        self.push_button.config(state=tk.DISABLED)
        self.reconcile_button.config(state=tk.DISABLED)
        self.swap_button.config(state=tk.DISABLED)

    # Operation button handlers (stubs for now)

    def on_pull(self):
        """Handle Pull button click."""
        if self.operation_in_progress:
            messagebox.showwarning("Operation in Progress", "An operation is already in progress. Please wait for it to complete.")
            return

        if not self.sync_ops:
            messagebox.showerror("Error", "Sync operations not initialized")
            return

        # Show log panel if not visible
        if not self.log_panel_visible:
            self.toggle_log_panel()

        self.log_message("=" * 60)
        self.log_message("Pull operation initiated...")
        self.update_status_bar("Pulling files from server...")

        # Disable operation buttons during operation
        self.disable_operations()
        self.operation_in_progress = True

        # Run pull operation in separate thread to keep GUI responsive
        def run_pull():
            try:
                # Progress callback to update GUI
                def progress_callback(message, current, total):
                    # Update GUI from separate thread using after()
                    self.root.after(0, lambda: self._update_pull_progress(message, current, total))

                # Execute pull operation
                success = self.sync_ops.pull(self.current_service, progress_callback)

                # Update GUI based on result
                self.root.after(0, lambda: self._pull_complete(success))

            except Exception as e:
                self.root.after(0, lambda: self._pull_error(str(e)))

        # Start pull in background thread
        pull_thread = threading.Thread(target=run_pull, daemon=True)
        pull_thread.start()

    def _update_pull_progress(self, message: str, current: int, total: int):
        """Update GUI during pull operation."""
        self.last_operation_message = message  # Store for admin cancellation detection
        self.log_message(message)
        if total > 0:
            progress_pct = (current / total) * 100
            self.update_status_bar(f"Pull: {message} ({progress_pct:.0f}%)")
        else:
            self.update_status_bar(f"Pull: {message}")

    def _pull_complete(self, success: bool):
        """Handle pull operation completion."""
        self.operation_in_progress = False
        self.enable_operations()

        if success:
            self.log_message("Pull operation completed successfully!")
            self.update_status_bar("Pull completed successfully")
            messagebox.showinfo("Pull Complete", "Files synchronized successfully from server.")
        else:
            # Check if operation was cancelled by administrator
            if "cancelled by administrator" in self.last_operation_message.lower():
                self.log_message("Pull operation cancelled by administrator.")
                self.update_status_bar("Pull cancelled by administrator")
                messagebox.showwarning("Operation Cancelled",
                                      "Pull operation was cancelled by the administrator.\n\n"
                                      "All changes have been rolled back.")
            else:
                self.log_message("Pull operation failed.")
                self.update_status_bar("Pull failed")
                messagebox.showerror("Pull Failed", "Failed to synchronize files from server. Check log for details.")

    def _pull_error(self, error_message: str):
        """Handle pull operation error."""
        self.operation_in_progress = False
        self.enable_operations()
        self.log_message(f"ERROR: {error_message}")
        self.update_status_bar("Pull failed with error")
        messagebox.showerror("Pull Error", f"Pull operation failed:\n{error_message}")

    def on_push(self):
        """Handle Push button click."""
        if self.operation_in_progress:
            messagebox.showwarning("Operation in Progress", "An operation is already in progress. Please wait for it to complete.")
            return

        if not self.sync_ops:
            messagebox.showerror("Error", "Sync operations not initialized")
            return

        # Show log panel if not visible
        if not self.log_panel_visible:
            self.toggle_log_panel()

        self.log_message("=" * 60)
        self.log_message("Push operation initiated...")
        self.update_status_bar("Pushing files to server...")

        # Disable operation buttons during operation
        self.disable_operations()
        self.operation_in_progress = True

        # Run push operation in separate thread to keep GUI responsive
        def run_push():
            try:
                # Progress callback to update GUI
                def progress_callback(message, current, total):
                    # Use after() to safely update GUI from background thread
                    self.root.after(0, lambda: self._update_push_progress(message, current, total))

                # Execute push operation
                success = self.sync_ops.push(self.current_service, progress_callback)

                # Update GUI with result (must use after() for thread safety)
                self.root.after(0, lambda: self._push_complete(success))

            except Exception as e:
                # Handle unexpected errors
                self.root.after(0, lambda: self._push_error(str(e)))

        # Start push operation in background thread
        push_thread = threading.Thread(target=run_push, daemon=True)
        push_thread.start()

    def _update_push_progress(self, message: str, current: int, total: int):
        """Update GUI during push operation."""
        self.last_operation_message = message  # Store for admin cancellation detection
        self.log_message(message)
        if total > 0:
            progress_pct = (current / total) * 100
            self.update_status_bar(f"Push: {message} ({progress_pct:.0f}%)")

    def _push_complete(self, success: bool):
        """Handle push operation completion."""
        self.operation_in_progress = False
        self.enable_operations()

        if success:
            self.log_message("Push operation completed successfully!")
            self.update_status_bar("Push completed successfully")
            messagebox.showinfo("Push Complete", "Files synchronized successfully to server.")
        else:
            # Check if operation was cancelled by administrator
            if "cancelled by administrator" in self.last_operation_message.lower():
                self.log_message("Push operation cancelled by administrator.")
                self.update_status_bar("Push cancelled by administrator")
                messagebox.showwarning("Operation Cancelled",
                                      "Push operation was cancelled by the administrator.\n\n"
                                      "All changes have been rolled back.")
            else:
                self.log_message("Push operation failed.")
                self.update_status_bar("Push failed")
                messagebox.showerror("Push Failed", "Failed to synchronize files to server. Check log for details.")

    def _push_error(self, error_message: str):
        """Handle push operation error."""
        self.operation_in_progress = False
        self.enable_operations()
        self.log_message(f"ERROR: {error_message}")
        self.update_status_bar("Push failed with error")
        messagebox.showerror("Push Error", f"Push operation failed:\n{error_message}")

    def on_reconcile(self):
        """Handle Reconcile button click."""
        if self.operation_in_progress:
            messagebox.showwarning("Operation in Progress", "An operation is already in progress. Please wait for it to complete.")
            return

        if not self.sync_ops:
            messagebox.showerror("Error", "Sync operations not initialized")
            return

        # Show log panel if not visible
        if not self.log_panel_visible:
            self.toggle_log_panel()

        self.log_message("=" * 60)
        self.log_message("Reconcile operation initiated...")
        self.update_status_bar("Reconciling files with server...")

        # Disable operation buttons during operation
        self.disable_operations()
        self.operation_in_progress = True

        # Run reconcile operation in separate thread to keep GUI responsive
        def run_reconcile():
            try:
                # Progress callback to update GUI
                def progress_callback(message, current, total):
                    # Use after() to safely update GUI from background thread
                    self.root.after(0, lambda: self._update_reconcile_progress(message, current, total))

                # Execute reconcile operation (newest file always wins)
                success = self.sync_ops.reconcile(
                    self.current_service,
                    progress_callback
                )

                # Update GUI with result (must use after() for thread safety)
                self.root.after(0, lambda: self._reconcile_complete(success))

            except Exception as e:
                # Handle unexpected errors
                self.root.after(0, lambda: self._reconcile_error(str(e)))

        # Start reconcile operation in background thread
        reconcile_thread = threading.Thread(target=run_reconcile, daemon=True)
        reconcile_thread.start()

    def _update_reconcile_progress(self, message: str, current: int, total: int):
        """Update GUI during reconcile operation."""
        self.last_operation_message = message  # Store for admin cancellation detection
        self.log_message(message)
        if total > 0:
            progress_pct = (current / total) * 100
            self.update_status_bar(f"Reconcile: {message} ({progress_pct:.0f}%)")

    def _reconcile_complete(self, success: bool):
        """Handle reconcile operation completion."""
        self.operation_in_progress = False
        self.enable_operations()

        if success:
            self.log_message("Reconcile operation completed successfully!")
            self.update_status_bar("Reconcile completed successfully")
            messagebox.showinfo("Reconcile Complete", "Files synchronized successfully (bidirectional sync).")
        else:
            # Check if operation was cancelled by administrator
            if "cancelled by administrator" in self.last_operation_message.lower():
                self.log_message("Reconcile operation cancelled by administrator.")
                self.update_status_bar("Reconcile cancelled by administrator")
                messagebox.showwarning("Operation Cancelled",
                                      "Reconcile operation was cancelled by the administrator.\n\n"
                                      "All changes have been rolled back.")
            else:
                self.log_message("Reconcile operation failed.")
                self.update_status_bar("Reconcile failed")
                messagebox.showerror("Reconcile Failed", "Failed to synchronize files. Check log for details.")

    def _reconcile_error(self, error_message: str):
        """Handle reconcile operation error."""
        self.operation_in_progress = False
        self.enable_operations()
        self.log_message(f"ERROR: {error_message}")
        self.update_status_bar("Reconcile failed with error")
        messagebox.showerror("Reconcile Error", f"Reconcile operation failed:\n{error_message}")

    def on_swap(self):
        """Handle Swap button click."""
        self.log_message("Swap operation initiated...")
        self.update_status_bar("Swapping service folders...")

        # Verify folder manager is initialized
        if not self.folder_mgr:
            error_msg = "Folder manager not initialized"
            self.log_message(f"ERROR: {error_msg}")
            self.update_status_bar("Swap failed")
            messagebox.showerror("Swap Error", error_msg)
            return

        # Call folder manager to perform swap
        success, message, new_service = self.folder_mgr.swap_service_folders()

        # Log the result
        self.log_message(message)

        if success:
            # Update service indicator with new service type
            self.update_service_indicator(new_service)
            self.update_status_bar(f"Swapped to {new_service} service")
            self.log_message(f"Swap completed successfully - Now using {new_service} service")

            # Show success notification
            messagebox.showinfo("Swap Complete", f"Successfully swapped to {new_service} service")
        else:
            # Show error
            self.update_status_bar("Swap failed")
            messagebox.showerror("Swap Error", message)

    def show_settings(self, first_run=False):
        """
        Show the settings dialog.

        Args:
            first_run: If True, indicates this is first-run setup requiring credentials
        """
        SettingsDialog(self.root, self.config_mgr, self.api, self, first_run=first_run)

    def show_revision_history(self):
        """Show the revision history dialog."""
        RevisionHistoryDialog(self.root, self.api, self.config_mgr)

    def show_about(self):
        """Show the About dialog."""
        about_text = (
            "AlderSync\n"
            "ProPresenter File Synchronization Client\n\n"
            f"Version: {VERSION}\n\n"
            "Synchronizes ProPresenter files between\n"
            "volunteers and church NAS server."
        )
        messagebox.showinfo("About AlderSync", about_text)

    def check_for_updates_and_prompt(self):
        """
        Check for client updates and prompt user to install if available.

        This is called after successful login to check if a newer version
        of the client is available on the server.
        """
        if not self.api:
            return

        try:
            # Create updater instance
            updater = ClientUpdater(self.api)

            # Check for updates
            self.log_message("Checking for client updates...")
            update_available, latest_version = updater.check_for_updates()

            if update_available:
                # Show update prompt dialog
                self.log_message(f"Update available: version {latest_version}")

                response = messagebox.askyesno(
                    "Update Available",
                    f"A new version of AlderSync is available!\n\n"
                    f"Current version: {VERSION}\n"
                    f"Latest version: {latest_version}\n\n"
                    f"Would you like to download and install the update now?\n\n"
                    f"The application will restart after the update.",
                    icon='info'
                )

                if response:
                    # User chose to update
                    self.log_message("User accepted update. Starting download...")
                    self.update_status_bar("Downloading update...")

                    try:
                        # Download and install update
                        # This will exit the application and restart with new version
                        updater.download_and_install_update()

                        # If we reach here, update failed
                        self.log_message("Update installation failed")
                        self.update_status_bar("Update failed")
                        messagebox.showerror(
                            "Update Failed",
                            "Failed to install update. Please try again later or contact support."
                        )

                    except Exception as e:
                        self.log_message(f"Update error: {e}")
                        self.update_status_bar("Update failed")
                        messagebox.showerror(
                            "Update Error",
                            f"Failed to download or install update:\n{e}"
                        )
                else:
                    # User declined update
                    self.log_message("User declined update")
            else:
                self.log_message(f"Client is up to date (version {VERSION})")

        except AlderSyncServerError as e:
            # Update check failed - log but don't interrupt startup
            self.log_message(f"Update check failed: {e}")
            logger.warning(f"Failed to check for updates: {e}")
        except Exception as e:
            # Unexpected error - log but don't interrupt startup
            self.log_message(f"Update check error: {e}")
            logger.error(f"Unexpected error checking for updates: {e}")

    def startup_login(self):
        """
        Perform startup login flow.

        Checks if credentials exist. If not, shows setup dialog.
        If yes, attempts auto-login and enables operations on success.
        """
        # Load configuration
        config = self.config_mgr.load_config()

        # Check if credentials exist
        credentials = self.config_mgr.get_credentials()

        if not credentials:
            # First run - show settings dialog for configuration
            self.update_status_bar("First time setup required")
            self.show_settings(first_run=True)
        else:
            # Credentials exist - attempt auto-login
            self.update_status_bar("Logging in...")
            username, password = credentials

            # Initialize API client
            server_url = config.get("server_url")
            server_port = config.get("server_port")
            verify_ssl = config.get("verify_ssl")

            self.api = AlderSyncAPI(server_url, server_port, verify_ssl)

            # Attempt login
            try:
                success = self.api.login(username, password)
                if success:
                    # Login successful
                    self.log_message(f"Logged in as {username}")
                    self.update_status_bar(f"Logged in as {username}")

                    # Initialize folder manager with documents path from config
                    documents_path = config.get("documents_path")
                    self.folder_mgr = FolderManager(documents_path)

                    # Validate folder state
                    validation_state, service_type = self.folder_mgr.validate_folder_state()

                    if validation_state == FolderValidationState.VALID:
                        # Folder state is valid - enable operations and update service indicator
                        # Initialize sync operations
                        self.sync_ops = SyncOperations(self.api, self.folder_mgr, self.config_mgr)

                        self.enable_operations()
                        self.update_service_indicator(service_type)
                        self.log_message(f"Folder validation successful - Current service: {service_type}")
                        self.update_status_bar(f"Logged in as {username} - {service_type} service active")

                        # Check for client updates after successful initialization
                        self.root.after(1000, self.check_for_updates_and_prompt)
                    elif validation_state == FolderValidationState.NO_ALTERNATE_FOUND:
                        # No alternate folder - ask user which service type they're working on
                        selected_service = self.show_service_type_selection_dialog()
                        if selected_service:
                            # User selected a service type - create alternate and continue
                            self.create_alternate_and_initialize(selected_service, username)
                        else:
                            # User cancelled - keep operations disabled
                            self.update_status_bar("Setup incomplete - alternate folder needed")
                    else:
                        # Other folder state errors - show error and keep operations disabled
                        error_message = get_validation_error_message(validation_state)
                        self.log_message(f"Folder validation failed: {error_message}")
                        self.update_status_bar("Folder validation error")
                        messagebox.showerror("Folder Validation Error", error_message)
                        # Operations remain disabled
                else:
                    # Login failed
                    self.update_status_bar("Login failed")
                    messagebox.showerror("Login Failed", "Authentication failed. Please check your credentials in Settings.")
                    self.api = None
            except AlderSyncAuthError as e:
                self.update_status_bar("Authentication error")
                messagebox.showerror("Login Failed", f"Authentication error: {e}\n\nPlease update credentials in Settings.")
                self.api = None
            except AlderSyncServerError as e:
                self.update_status_bar("Server connection error")
                messagebox.showerror("Connection Error", f"Cannot connect to server: {e}\n\nPlease check server settings in Settings menu.")
                self.api = None

    def show_service_type_selection_dialog(self) -> Optional[str]:
        """
        Show dialog asking user which service type they're currently working on.

        This is shown when no alternate folder exists (first-time setup scenario).

        Returns:
            "Contemporary" or "Traditional" if user selects a service type,
            None if user cancels
        """
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Service Type")
        dialog.geometry("450x250")
        dialog.resizable(False, False)

        # Make dialog modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog on parent window
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Result will be stored here
        result = {"service": None}

        # Header
        header = tk.Label(dialog, text="Initial Service Setup",
                         font=("Arial", 14, "bold"))
        header.pack(pady=(20, 10))

        # Question text
        question = tk.Label(dialog,
                           text="Which service type are you currently working on?",
                           font=("Arial", 11))
        question.pack(pady=(0, 10))

        # Info text
        info = tk.Label(dialog,
                       text="This will create the appropriate alternate folder\n"
                            "so you can swap between service types.",
                       font=("Arial", 9), foreground="gray")
        info.pack(pady=(0, 20))

        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_contemporary():
            """User selected Contemporary service."""
            result["service"] = "Contemporary"
            dialog.destroy()

        def select_traditional():
            """User selected Traditional service."""
            result["service"] = "Traditional"
            dialog.destroy()

        def cancel_selection():
            """User cancelled."""
            result["service"] = None
            dialog.destroy()

        # Contemporary button
        contemporary_btn = tk.Button(button_frame, text="Contemporary",
                                     command=select_contemporary,
                                     width=15, font=("Arial", 11))
        contemporary_btn.pack(side=tk.LEFT, padx=10)

        # Traditional button
        traditional_btn = tk.Button(button_frame, text="Traditional",
                                   command=select_traditional,
                                   width=15, font=("Arial", 11))
        traditional_btn.pack(side=tk.LEFT, padx=10)

        # Cancel button (smaller, at bottom)
        cancel_btn = tk.Button(dialog, text="Cancel",
                              command=cancel_selection,
                              width=10, font=("Arial", 9))
        cancel_btn.pack(pady=(10, 20))

        # Wait for dialog to close
        dialog.wait_window()

        return result["service"]

    def create_alternate_and_initialize(self, selected_service: str, username: str):
        """
        Create alternate folder based on user's selected service type and initialize the app.

        Args:
            selected_service: "Contemporary" or "Traditional" - the service user is working on
            username: Username for status display
        """
        # Determine which alternate folder to create
        # If user selected Contemporary, they're working on Contemporary,
        # so we need to create Traditional as the alternate
        if selected_service == "Contemporary":
            alternate_to_create = "Traditional"
        else:  # Traditional
            alternate_to_create = "Contemporary"

        self.log_message(f"User selected {selected_service} service")
        self.log_message(f"Creating {alternate_to_create} alternate folder...")

        # Create the alternate folder
        create_message = self.folder_mgr.auto_create_alternate_folder(alternate_to_create)
        self.log_message(create_message)

        # Update config to set default service type
        self.config_mgr.set("default_service_type", selected_service)
        self.log_message(f"Set default service type to {selected_service}")

        # Re-validate folder state
        validation_state, detected_service_type = self.folder_mgr.validate_folder_state()

        if validation_state == FolderValidationState.VALID:
            # Success - initialize operations
            self.sync_ops = SyncOperations(self.api, self.folder_mgr, self.config_mgr)
            self.enable_operations()
            self.update_service_indicator(detected_service_type)
            self.log_message(f"Setup complete - Current service: {detected_service_type}")
            self.update_status_bar(f"Logged in as {username} - {detected_service_type} service active")

            # Show success message
            messagebox.showinfo("Setup Complete",
                              f"Successfully configured for {selected_service} service.\n\n"
                              f"You can now use AlderSync to sync your ProPresenter files.")

            # Check for client updates after successful setup
            self.root.after(1000, self.check_for_updates_and_prompt)
        else:
            # Still failed - show error
            error_message = get_validation_error_message(validation_state)
            self.log_message(f"Setup failed: {error_message}")
            self.update_status_bar("Setup failed")
            messagebox.showerror("Setup Failed",
                               f"Failed to complete setup:\n\n{error_message}")

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def launch_gui():
    """Launch the AlderSync GUI application."""
    app = AlderSyncGUI()
    app.run()
