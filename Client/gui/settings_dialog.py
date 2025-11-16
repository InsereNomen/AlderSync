"""
AlderSync Client - Settings Dialog Module

Implements the Settings dialog window with tabbed interface.

Author: AlderSync Project
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from managers import ConfigManager, FolderManager
from models import FolderValidationState, get_validation_error_message
from api import AlderSyncAPI
from exceptions import AlderSyncAuthError, AlderSyncServerError
from operations import SyncOperations


class SettingsDialog:
    """
    Settings dialog window with tabbed interface.

    Implements settings UI per Specification.md section 4.1.2.
    Currently implements Connection tab (Task 6.1).
    Additional tabs will be added in Task 6.2.
    """

    def __init__(self, parent, config_mgr: ConfigManager, api, gui_parent=None, first_run=False):
        """
        Initialize settings dialog.

        Args:
            parent: Parent tkinter window
            config_mgr: Configuration manager instance
            api: AlderSyncAPI instance for password changes (can be None if not logged in)
            gui_parent: Reference to main GUI instance (for first-run authentication)
            first_run: If True, this is first-run setup requiring authentication
        """
        self.parent = parent
        self.config_mgr = config_mgr
        self.api = api
        self.gui_parent = gui_parent
        self.first_run = first_run

        # Create toplevel dialog window
        self.dialog = tk.Toplevel(parent)
        if first_run:
            self.dialog.title("AlderSync - First Time Setup")
        else:
            self.dialog.title("Settings")
        self.dialog.geometry("500x520")
        self.dialog.minsize(450, 480)

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog on parent window
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Dictionary to store field variables
        self.fields = {}

        # Create UI components
        # IMPORTANT: Create buttons BEFORE tabs so they're visible at the bottom
        # Tkinter pack() order matters - items packed with side=BOTTOM should be packed first
        self.create_buttons()
        self.create_tabs()

        # Load current configuration values
        self.load_config()

        # Handle window close button (X)
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_tabs(self):
        """Create tabbed notebook interface."""
        # Create notebook (tabbed container)
        self.notebook = ttk.Notebook(self.dialog)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create all tabs
        self.create_connection_tab()
        self.create_service_tab()
        self.create_paths_tab()
        self.create_logging_tab()
        self.create_behavior_tab()
        self.create_password_tab()

    def create_connection_tab(self):
        """Create Connection settings tab."""
        # Create frame for Connection tab
        conn_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(conn_frame, text="Connection")

        current_row = 0

        # Server URL field
        url_label = ttk.Label(conn_frame, text="Server URL:", font=("Arial", 10))
        url_label.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        self.fields['server_url'] = tk.StringVar()
        url_entry = ttk.Entry(conn_frame, textvariable=self.fields['server_url'],
                             width=40, font=("Arial", 10))
        url_entry.grid(row=current_row, column=0, sticky=tk.W+tk.E, pady=(0, 15))
        current_row += 1

        # Add tooltip/hint
        url_hint = ttk.Label(conn_frame, text="Example: https://church-nas.local or http://192.168.1.100",
                            font=("Arial", 8), foreground="gray")
        url_hint.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 15))
        current_row += 1

        # Server Port field
        port_label = ttk.Label(conn_frame, text="Server Port:", font=("Arial", 10))
        port_label.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        self.fields['server_port'] = tk.StringVar()
        port_entry = ttk.Entry(conn_frame, textvariable=self.fields['server_port'],
                              width=10, font=("Arial", 10))
        port_entry.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 15))
        current_row += 1

        # Add tooltip/hint
        port_hint = ttk.Label(conn_frame, text="Default: 8000 (HTTP) or 443 (HTTPS)",
                             font=("Arial", 8), foreground="gray")
        port_hint.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 15))
        current_row += 1

        # Verify SSL checkbox
        self.fields['verify_ssl'] = tk.BooleanVar()
        ssl_check = ttk.Checkbutton(conn_frame, text="Verify SSL Certificate",
                                    variable=self.fields['verify_ssl'])
        ssl_check.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        # SSL hint
        ssl_hint = ttk.Label(conn_frame,
                            text="Uncheck if using self-signed certificates (common for NAS servers)",
                            font=("Arial", 8), foreground="gray",
                            wraplength=400)
        ssl_hint.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 15))
        current_row += 1

        # Username field
        username_label = ttk.Label(conn_frame, text="Username:", font=("Arial", 10))
        username_label.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        self.fields['username'] = tk.StringVar()
        username_entry = ttk.Entry(conn_frame, textvariable=self.fields['username'],
                                   width=30, font=("Arial", 10))
        username_entry.grid(row=current_row, column=0, sticky=tk.W+tk.E, pady=(0, 15))
        current_row += 1

        # Password field
        password_label = ttk.Label(conn_frame, text="Password:", font=("Arial", 10))
        password_label.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        self.fields['password'] = tk.StringVar()
        password_entry = ttk.Entry(conn_frame, textvariable=self.fields['password'],
                                   width=30, font=("Arial", 10), show="*")
        password_entry.grid(row=current_row, column=0, sticky=tk.W+tk.E, pady=(0, 15))
        current_row += 1

        # Credentials hint (only show on first run)
        if self.first_run:
            creds_hint = ttk.Label(conn_frame,
                                  text="Enter your AlderSync server credentials to continue",
                                  font=("Arial", 8, "bold"), foreground="blue",
                                  wraplength=400)
            creds_hint.grid(row=current_row, column=0, sticky=tk.W, pady=(0, 15))
            current_row += 1

        # Configure grid column to expand
        conn_frame.columnconfigure(0, weight=1)

    def create_service_tab(self):
        """Create Service settings tab."""
        # Create frame for Service tab
        service_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(service_frame, text="Service")

        # Default service type field
        service_label = ttk.Label(service_frame, text="Default Service Type:", font=("Arial", 10))
        service_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['default_service_type'] = tk.StringVar()
        service_combo = ttk.Combobox(service_frame, textvariable=self.fields['default_service_type'],
                                     values=["Contemporary", "Traditional"],
                                     state="readonly", width=20, font=("Arial", 10))
        service_combo.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Add tooltip/hint
        service_hint = ttk.Label(service_frame,
                                text="This determines which ProPresenter folder is active by default",
                                font=("Arial", 8), foreground="gray",
                                wraplength=400)
        service_hint.grid(row=2, column=0, sticky=tk.W, pady=(0, 15))

        # Configure grid column to expand
        service_frame.columnconfigure(0, weight=1)

    def create_paths_tab(self):
        """Create Paths settings tab."""
        # Create frame for Paths tab
        paths_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(paths_frame, text="Paths")

        # Documents folder path field
        docs_label = ttk.Label(paths_frame, text="Custom Documents Folder Path:", font=("Arial", 10))
        docs_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['documents_path'] = tk.StringVar()
        docs_entry = ttk.Entry(paths_frame, textvariable=self.fields['documents_path'],
                              width=50, font=("Arial", 10))
        docs_entry.grid(row=1, column=0, sticky=tk.W+tk.E, pady=(0, 5))

        # Browse button
        browse_btn = ttk.Button(paths_frame, text="Browse...", command=self.browse_documents_folder)
        browse_btn.grid(row=1, column=1, padx=(5, 0))

        # Add tooltip/hint
        docs_hint = ttk.Label(paths_frame,
                            text="Leave blank to use default Documents folder. Use this to override the location where ProPresenter files are stored.",
                            font=("Arial", 8), foreground="gray",
                            wraplength=450)
        docs_hint.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        # Configure grid columns to expand
        paths_frame.columnconfigure(0, weight=1)

    def create_logging_tab(self):
        """Create Logging settings tab."""
        # Create frame for Logging tab
        logging_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(logging_frame, text="Logging")

        # Log level field
        level_label = ttk.Label(logging_frame, text="Log Level:", font=("Arial", 10))
        level_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['log_level'] = tk.StringVar()
        level_combo = ttk.Combobox(logging_frame, textvariable=self.fields['log_level'],
                                   values=["DEBUG", "INFO", "WARNING", "ERROR"],
                                   state="readonly", width=15, font=("Arial", 10))
        level_combo.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Add tooltip/hint
        level_hint = ttk.Label(logging_frame,
                              text="DEBUG shows all details, INFO shows major operations, WARNING/ERROR show only issues",
                              font=("Arial", 8), foreground="gray",
                              wraplength=400)
        level_hint.grid(row=2, column=0, sticky=tk.W, pady=(0, 15))

        # Log retention days field
        retention_label = ttk.Label(logging_frame, text="Log Retention (days):", font=("Arial", 10))
        retention_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['log_retention_days'] = tk.StringVar()
        retention_entry = ttk.Entry(logging_frame, textvariable=self.fields['log_retention_days'],
                                   width=10, font=("Arial", 10))
        retention_entry.grid(row=4, column=0, sticky=tk.W, pady=(0, 15))

        # Add tooltip/hint
        retention_hint = ttk.Label(logging_frame,
                                  text="Logs older than this many days will be automatically deleted",
                                  font=("Arial", 8), foreground="gray",
                                  wraplength=400)
        retention_hint.grid(row=5, column=0, sticky=tk.W, pady=(0, 15))

        # Show log on startup checkbox
        self.fields['show_log_on_startup'] = tk.BooleanVar()
        show_log_check = ttk.Checkbutton(logging_frame, text="Show log panel on startup",
                                        variable=self.fields['show_log_on_startup'])
        show_log_check.grid(row=6, column=0, sticky=tk.W, pady=(0, 5))

        # Add tooltip/hint
        show_log_hint = ttk.Label(logging_frame,
                                 text="When enabled, the log panel will be visible when the application starts",
                                 font=("Arial", 8), foreground="gray",
                                 wraplength=400)
        show_log_hint.grid(row=7, column=0, sticky=tk.W, pady=(0, 15))

        # Configure grid column to expand
        logging_frame.columnconfigure(0, weight=1)

    def create_behavior_tab(self):
        """Create Behavior settings tab."""
        # Create frame for Behavior tab
        behavior_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(behavior_frame, text="Behavior")

        # Confirm before push checkbox
        self.fields['confirm_before_push'] = tk.BooleanVar()
        confirm_check = ttk.Checkbutton(behavior_frame, text="Confirm before Push",
                                       variable=self.fields['confirm_before_push'])
        confirm_check.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        # Add tooltip/hint
        confirm_hint = ttk.Label(behavior_frame,
                               text="When enabled, a confirmation dialog will appear before uploading files to the server",
                               font=("Arial", 8), foreground="gray",
                               wraplength=400)
        confirm_hint.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Configure grid column to expand
        behavior_frame.columnconfigure(0, weight=1)

    def create_password_tab(self):
        """Create Change Password tab."""
        # Create frame for Password tab
        password_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(password_frame, text="Password")

        # Header
        header_label = ttk.Label(password_frame, text="Change Password",
                                 font=("Arial", 12, "bold"))
        header_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        # Current Password field
        current_pw_label = ttk.Label(password_frame, text="Current Password:", font=("Arial", 10))
        current_pw_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['current_password'] = tk.StringVar()
        current_pw_entry = ttk.Entry(password_frame, textvariable=self.fields['current_password'],
                                     width=30, font=("Arial", 10), show="*")
        current_pw_entry.grid(row=2, column=0, sticky=tk.W+tk.E, pady=(0, 15))

        # New Password field
        new_pw_label = ttk.Label(password_frame, text="New Password:", font=("Arial", 10))
        new_pw_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['new_password'] = tk.StringVar()
        new_pw_entry = ttk.Entry(password_frame, textvariable=self.fields['new_password'],
                                 width=30, font=("Arial", 10), show="*")
        new_pw_entry.grid(row=4, column=0, sticky=tk.W+tk.E, pady=(0, 15))

        # Confirm New Password field
        confirm_pw_label = ttk.Label(password_frame, text="Confirm New Password:", font=("Arial", 10))
        confirm_pw_label.grid(row=5, column=0, sticky=tk.W, pady=(0, 5))

        self.fields['confirm_password'] = tk.StringVar()
        confirm_pw_entry = ttk.Entry(password_frame, textvariable=self.fields['confirm_password'],
                                     width=30, font=("Arial", 10), show="*")
        confirm_pw_entry.grid(row=6, column=0, sticky=tk.W+tk.E, pady=(0, 20))

        # Change Password button
        change_pw_btn = ttk.Button(password_frame, text="Change Password",
                                   command=self.change_password)
        change_pw_btn.grid(row=7, column=0, sticky=tk.W, pady=(0, 15))

        # Info label
        info_label = ttk.Label(password_frame,
                              text="After changing your password, you will continue to be logged in.\n"
                                   "The new password will be used for future logins.",
                              font=("Arial", 8), foreground="gray",
                              wraplength=400)
        info_label.grid(row=8, column=0, sticky=tk.W, pady=(0, 15))

        # Configure grid column to expand
        password_frame.columnconfigure(0, weight=1)

    def browse_documents_folder(self):
        """Open folder browser to select custom Documents folder."""
        current_path = self.fields['documents_path'].get()
        initial_dir = current_path if current_path else str(Path.home())

        folder = filedialog.askdirectory(
            parent=self.dialog,
            title="Select Documents Folder",
            initialdir=initial_dir
        )

        if folder:
            self.fields['documents_path'].set(folder)

    def create_buttons(self):
        """Create Save and Cancel buttons."""
        # Button frame at bottom
        button_frame = ttk.Frame(self.dialog, padding=10)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # Save button
        save_btn = ttk.Button(button_frame, text="Save", command=self.save_settings)
        save_btn.pack(side=tk.RIGHT, padx=5)

    def load_config(self):
        """Load current configuration values into fields."""
        # Load Connection tab values
        self.fields['server_url'].set(self.config_mgr.get('server_url', 'https://localhost'))
        self.fields['server_port'].set(str(self.config_mgr.get('server_port', 8000)))
        self.fields['verify_ssl'].set(self.config_mgr.get('verify_ssl', False))

        # Load username (password is never loaded for security)
        username = self.config_mgr.get('username', '')
        self.fields['username'].set(username if username else '')
        self.fields['password'].set('')  # Never pre-fill password

        # Load Service tab values
        self.fields['default_service_type'].set(self.config_mgr.get('default_service_type', 'Contemporary'))

        # Load Paths tab values
        docs_path = self.config_mgr.get('documents_path', None)
        self.fields['documents_path'].set(docs_path if docs_path else '')

        # Load Logging tab values
        self.fields['log_level'].set(self.config_mgr.get('log_level', 'INFO'))
        self.fields['log_retention_days'].set(str(self.config_mgr.get('log_retention_days', 30)))
        self.fields['show_log_on_startup'].set(self.config_mgr.get('show_log_on_startup', False))

        # Load Behavior tab values
        self.fields['confirm_before_push'].set(self.config_mgr.get('confirm_before_push', True))

    def validate_inputs(self) -> bool:
        """
        Validate all input fields.

        Returns:
            True if all inputs are valid, False otherwise
        """
        # Validate server URL
        url = self.fields['server_url'].get().strip()
        if not url:
            messagebox.showerror("Validation Error",
                               "Server URL cannot be empty.",
                               parent=self.dialog)
            return False

        # Check URL starts with http:// or https://
        if not (url.startswith('http://') or url.startswith('https://')):
            messagebox.showerror("Validation Error",
                               "Server URL must start with http:// or https://",
                               parent=self.dialog)
            return False

        # Validate server port
        port_str = self.fields['server_port'].get().strip()
        if not port_str:
            messagebox.showerror("Validation Error",
                               "Server Port cannot be empty.",
                               parent=self.dialog)
            return False

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError("Port out of range")
        except ValueError:
            messagebox.showerror("Validation Error",
                               "Server Port must be a number between 1 and 65535.",
                               parent=self.dialog)
            return False

        # Validate documents path (if provided)
        docs_path = self.fields['documents_path'].get().strip()
        if docs_path:
            # Check if path exists
            if not Path(docs_path).exists():
                messagebox.showerror("Validation Error",
                                   "Documents path does not exist.\n\n"
                                   f"Path: {docs_path}",
                                   parent=self.dialog)
                return False

            # Check if it's a directory
            if not Path(docs_path).is_dir():
                messagebox.showerror("Validation Error",
                                   "Documents path must be a directory, not a file.",
                                   parent=self.dialog)
                return False

        # Validate log retention days
        retention_str = self.fields['log_retention_days'].get().strip()
        if not retention_str:
            messagebox.showerror("Validation Error",
                               "Log retention days cannot be empty.",
                               parent=self.dialog)
            return False

        try:
            retention = int(retention_str)
            if retention < 1:
                raise ValueError("Retention must be positive")
        except ValueError:
            messagebox.showerror("Validation Error",
                               "Log retention days must be a positive number.",
                               parent=self.dialog)
            return False

        return True

    def change_password(self):
        """
        Handle password change request.

        Validates inputs, calls API to change password, and updates keyring on success.
        """
        # Check if logged in
        if not self.api:
            messagebox.showerror("Not Logged In",
                               "You must be logged in to change your password.\n\n"
                               "Please restart the application and log in first.",
                               parent=self.dialog)
            return

        # Get field values
        current_password = self.fields['current_password'].get()
        new_password = self.fields['new_password'].get()
        confirm_password = self.fields['confirm_password'].get()

        # Validate inputs
        if not current_password:
            messagebox.showerror("Validation Error",
                               "Please enter your current password.",
                               parent=self.dialog)
            return

        if not new_password:
            messagebox.showerror("Validation Error",
                               "Please enter a new password.",
                               parent=self.dialog)
            return

        if not confirm_password:
            messagebox.showerror("Validation Error",
                               "Please confirm your new password.",
                               parent=self.dialog)
            return

        # Check that new passwords match
        if new_password != confirm_password:
            messagebox.showerror("Validation Error",
                               "New password and confirmation do not match.\n\n"
                               "Please try again.",
                               parent=self.dialog)
            # Clear the password fields
            self.fields['new_password'].set('')
            self.fields['confirm_password'].set('')
            return

        # Check that new password is different from current
        if new_password == current_password:
            messagebox.showerror("Validation Error",
                               "New password must be different from current password.",
                               parent=self.dialog)
            return

        # Attempt to change password via API
        try:
            success = self.api.change_password(current_password, new_password)

            if success:
                # Update stored password in keyring
                # Get username from config
                credentials = self.config_mgr.get_credentials()
                if credentials:
                    username, _ = credentials
                    self.config_mgr.store_credentials(username, new_password)

                # Show success message
                messagebox.showinfo("Password Changed",
                                  "Your password has been changed successfully.\n\n"
                                  "The new password will be used for future logins.",
                                  parent=self.dialog)

                # Clear password fields
                self.fields['current_password'].set('')
                self.fields['new_password'].set('')
                self.fields['confirm_password'].set('')

        except AlderSyncAuthError as e:
            # Authentication error - likely wrong current password
            messagebox.showerror("Authentication Error",
                               f"Failed to change password:\n\n{e}\n\n"
                               "Please verify your current password is correct.",
                               parent=self.dialog)
            # Clear current password field
            self.fields['current_password'].set('')

        except AlderSyncServerError as e:
            # Server error
            messagebox.showerror("Server Error",
                               f"Failed to change password:\n\n{e}\n\n"
                               "Please try again later.",
                               parent=self.dialog)

    def save_settings(self):
        """Save settings to configuration file and attempt authentication if credentials provided."""
        # Validate inputs first
        if not self.validate_inputs():
            return

        # Check if credentials are being set
        username = self.fields['username'].get().strip()
        password = self.fields['password'].get()
        credentials_provided = bool(username and password)

        # If this is first run or credentials are provided, attempt authentication
        if credentials_provided:
            # Validate credentials are provided on first run
            if self.first_run and (not username or not password):
                messagebox.showerror("Validation Error",
                                   "Username and password are required for first-time setup.",
                                   parent=self.dialog)
                return

            # Save connection settings first (needed for login)
            self.config_mgr.set('server_url', self.fields['server_url'].get().strip())
            self.config_mgr.set('server_port', int(self.fields['server_port'].get().strip()))
            self.config_mgr.set('verify_ssl', self.fields['verify_ssl'].get())

            # Initialize API client with new settings
            server_url = self.fields['server_url'].get().strip()
            server_port = int(self.fields['server_port'].get().strip())
            verify_ssl = self.fields['verify_ssl'].get()

            temp_api = AlderSyncAPI(server_url, server_port, verify_ssl)

            # Attempt login
            try:
                success = temp_api.login(username, password)
                if not success:
                    messagebox.showerror("Login Failed",
                                       "Authentication failed. Please check your username and password.",
                                       parent=self.dialog)
                    return

                # Login successful - store credentials
                self.config_mgr.store_credentials(username, password)

                # Update GUI parent's API reference if available
                if self.gui_parent:
                    self.gui_parent.api = temp_api

                    # For first run, initialize folder manager and operations
                    if self.first_run:
                        # Initialize folder manager
                        documents_path = self.fields['documents_path'].get().strip()
                        if not documents_path:
                            documents_path = None
                        self.gui_parent.folder_mgr = FolderManager(documents_path)

                        # Validate folder state
                        validation_state, detected_service_type = self.gui_parent.folder_mgr.validate_folder_state()

                        if validation_state == FolderValidationState.VALID:
                            # Folder state is valid - initialize sync operations
                            self.gui_parent.sync_ops = SyncOperations(temp_api, self.gui_parent.folder_mgr, self.config_mgr)
                            self.gui_parent.enable_operations()
                            self.gui_parent.update_service_indicator(detected_service_type)
                            self.gui_parent.log_message(f"Logged in as {username}")
                            self.gui_parent.log_message(f"Folder validation successful - Current service: {detected_service_type}")
                            self.gui_parent.update_status_bar(f"Logged in as {username} - {detected_service_type} service active")
                        elif validation_state == FolderValidationState.NO_ALTERNATE_FOUND:
                            # Need to select service type
                            # Close settings dialog first
                            self.dialog.destroy()
                            # Show service type selection
                            selected_service = self.gui_parent.show_service_type_selection_dialog()
                            if selected_service:
                                self.gui_parent.create_alternate_and_initialize(selected_service, username)
                            else:
                                self.gui_parent.update_status_bar("Setup incomplete - service type selection required")
                            return
                        else:
                            # Folder validation error
                            error_message = get_validation_error_message(validation_state)
                            messagebox.showerror("Folder Validation Error",
                                               error_message,
                                               parent=self.dialog)
                            self.gui_parent.update_status_bar("Folder validation error")
                            # Don't return - still save other settings

            except AlderSyncAuthError as e:
                messagebox.showerror("Authentication Error",
                                   f"Authentication failed: {e}\n\nPlease check your credentials.",
                                   parent=self.dialog)
                return
            except AlderSyncServerError as e:
                messagebox.showerror("Connection Error",
                                   f"Cannot connect to server: {e}\n\nPlease check your server settings.",
                                   parent=self.dialog)
                return

        # Save all other settings
        self.config_mgr.set('server_url', self.fields['server_url'].get().strip())
        self.config_mgr.set('server_port', int(self.fields['server_port'].get().strip()))
        self.config_mgr.set('verify_ssl', self.fields['verify_ssl'].get())
        self.config_mgr.set('default_service_type', self.fields['default_service_type'].get())

        docs_path = self.fields['documents_path'].get().strip()
        self.config_mgr.set('documents_path', docs_path if docs_path else None)

        self.config_mgr.set('log_level', self.fields['log_level'].get())
        self.config_mgr.set('log_retention_days', int(self.fields['log_retention_days'].get().strip()))
        self.config_mgr.set('show_log_on_startup', self.fields['show_log_on_startup'].get())
        self.config_mgr.set('confirm_before_push', self.fields['confirm_before_push'].get())

        # Show success message
        if credentials_provided and self.first_run:
            messagebox.showinfo("Setup Complete",
                              "Settings saved and authentication successful!",
                              parent=self.dialog)
        else:
            messagebox.showinfo("Settings Saved",
                              "Settings have been saved successfully.\n\n"
                              "Note: Some settings may require restarting the application to take effect.",
                              parent=self.dialog)

        # Close dialog
        self.dialog.destroy()

    def on_close(self):
        """
        Handle window close event (X button).
        Prompts user to save changes before closing.
        On first run, warns user that setup is required.
        """
        if self.first_run:
            # First run - warn user that setup is required
            result = messagebox.askokcancel(
                "Setup Required",
                "You must complete the initial setup to use AlderSync.\n\n"
                "Are you sure you want to exit without completing setup?",
                parent=self.dialog
            )
            if result:
                # User confirmed - close dialog and application
                self.dialog.destroy()
                # Exit the application since setup is incomplete
                if self.gui_parent:
                    self.gui_parent.root.quit()
        else:
            # Normal settings mode
            result = messagebox.askyesnocancel(
                "Save Settings?",
                "Do you want to save changes to settings?",
                parent=self.dialog
            )

            if result is True:
                # User clicked Yes - save and close
                self.save_settings()
                # save_settings() will close the dialog if successful
            elif result is False:
                # User clicked No - close without saving
                self.dialog.destroy()
            # If result is None, user clicked Cancel - do nothing (stay open)
