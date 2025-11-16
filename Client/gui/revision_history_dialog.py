"""
AlderSync Client - Revision History Dialog Module

Implements the Revision History viewer dialog.

Author: AlderSync Project
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
import hashlib
import logging

from managers import ConfigManager, FolderManager
from api import AlderSyncAPI
from exceptions import AlderSyncAuthError, AlderSyncServerError

# Configure logging
logger = logging.getLogger(__name__)


class RevisionHistoryDialog:
    """
    Revision History viewer dialog.

    Implements revision history UI per Specification.md section 4.1.3.
    Allows browsing and restoring previous file revisions.
    """

    def __init__(self, parent, api, config_mgr: ConfigManager):
        """
        Initialize revision history dialog.

        Args:
            parent: Parent tkinter window
            api: AlderSyncAPI instance for fetching revisions
            config_mgr: Configuration manager instance to get service type
        """
        self.parent = parent
        self.api = api
        self.config_mgr = config_mgr

        # Create toplevel dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Revision History")
        self.dialog.geometry("800x600")
        self.dialog.minsize(700, 500)

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # State variables
        self.current_service = None
        self.files_data = []  # List of file metadata with revision counts
        self.selected_file = None
        self.revisions_data = []  # List of revisions for selected file
        self.loading_label = None  # Progress indicator during loading
        self.last_gui_update = 0  # Timestamp of last GUI update for throttling

        # Create UI components
        self.create_ui()

        # Center dialog on parent window immediately after UI creation
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Show loading indicator and defer data loading so window appears first
        self.show_loading_indicator()
        self.dialog.after(100, self.load_files)

    def create_ui(self):
        """Create the revision history UI."""
        # Main container with two panes
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top section: Service selector and refresh
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # Service type label and selector
        service_label = ttk.Label(header_frame, text="Service Type:", font=("Arial", 10, "bold"))
        service_label.pack(side=tk.LEFT, padx=(0, 10))

        # Get current service type from config
        folder_mgr = FolderManager(self.config_mgr.get("documents_path"))
        _, service_type = folder_mgr.validate_folder_state()
        self.current_service = service_type if service_type else "Contemporary"

        service_var = tk.StringVar(value=self.current_service)
        service_combo = ttk.Combobox(header_frame, textvariable=service_var,
                                     values=["Contemporary", "Traditional"],
                                     state="readonly", width=15)
        service_combo.pack(side=tk.LEFT, padx=(0, 20))
        service_combo.bind("<<ComboboxSelected>>", lambda e: self.on_service_change(service_var.get()))

        # Refresh button
        refresh_btn = ttk.Button(header_frame, text="Refresh", command=self.load_files)
        refresh_btn.pack(side=tk.LEFT)

        # Create paned window for two-column layout
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left pane: File list
        left_frame = ttk.Frame(paned, padding=5)
        paned.add(left_frame, weight=1)

        # File list label
        file_list_label = ttk.Label(left_frame, text="Files with Revisions", font=("Arial", 10, "bold"))
        file_list_label.pack(anchor=tk.W, pady=(0, 5))

        # File list with scrollbar
        file_list_frame = ttk.Frame(left_frame)
        file_list_frame.pack(fill=tk.BOTH, expand=True)

        file_scrollbar = ttk.Scrollbar(file_list_frame)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(file_list_frame, yscrollcommand=file_scrollbar.set,
                                        font=("Arial", 9), activestyle='none')
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        file_scrollbar.config(command=self.file_listbox.yview)

        # Bind selection event
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        # Right pane: Revision details
        right_frame = ttk.Frame(paned, padding=5)
        paned.add(right_frame, weight=2)

        # Revision details label
        rev_label = ttk.Label(right_frame, text="Revision History", font=("Arial", 10, "bold"))
        rev_label.pack(anchor=tk.W, pady=(0, 5))

        # Info label showing selected file
        self.selected_file_label = ttk.Label(right_frame, text="Select a file to view revisions",
                                              font=("Arial", 9, "italic"), foreground="gray")
        self.selected_file_label.pack(anchor=tk.W, pady=(0, 10))

        # Revision tree view with scrollbar
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree_scrollbar = ttk.Scrollbar(tree_frame)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create treeview for revisions
        columns = ("Revision", "Size", "Modified", "User", "Changelist")
        self.revision_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                          yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.config(command=self.revision_tree.yview)

        # Configure columns
        self.revision_tree.heading("Revision", text="Revision")
        self.revision_tree.heading("Size", text="Size")
        self.revision_tree.heading("Modified", text="Modified")
        self.revision_tree.heading("User", text="User")
        self.revision_tree.heading("Changelist", text="Changelist ID")

        self.revision_tree.column("Revision", width=80, anchor=tk.CENTER)
        self.revision_tree.column("Size", width=100, anchor=tk.E)
        self.revision_tree.column("Modified", width=180, anchor=tk.W)
        self.revision_tree.column("User", width=120, anchor=tk.W)
        self.revision_tree.column("Changelist", width=100, anchor=tk.CENTER)

        self.revision_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Action buttons frame
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Save As button (formerly Download Revision)
        self.save_as_btn = ttk.Button(button_frame, text="Save As",
                                      command=self.save_as_revision, state=tk.DISABLED)
        self.save_as_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Pull Revision button
        self.pull_btn = ttk.Button(button_frame, text="Pull Revision",
                                   command=self.pull_revision, state=tk.DISABLED)
        self.pull_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Restore button
        self.restore_btn = ttk.Button(button_frame, text="Restore This Revision",
                                      command=self.restore_revision, state=tk.DISABLED)
        self.restore_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Info label (on separate line below buttons)
        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))

        info_label = ttk.Label(info_frame,
                              text="Save As: Save to custom location | Pull: Download to ProPresenter folder | Restore: Makes old revision current",
                              font=("Arial", 8), foreground="gray")
        info_label.pack(anchor=tk.W)

        # Bottom: Close button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        close_btn = ttk.Button(bottom_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

    def show_loading_indicator(self):
        """Show loading indicator overlay."""
        if not self.loading_label:
            # Create a frame to overlay on the dialog
            loading_frame = ttk.Frame(self.dialog, padding=20)
            loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

            # Create loading label
            self.loading_label = ttk.Label(
                loading_frame,
                text="Loading files...",
                font=("Arial", 12),
                foreground="gray"
            )
            self.loading_label.pack()

        self.loading_label.master.lift()  # Bring to front
        self.dialog.update_idletasks()

    def hide_loading_indicator(self):
        """Hide loading indicator overlay."""
        if self.loading_label:
            self.loading_label.master.place_forget()
            self.dialog.update_idletasks()

    def update_loading_indicator(self, message: str, force: bool = False):
        """
        Update loading indicator message.

        Args:
            message: New message to display
            force: If True, force immediate GUI update regardless of throttle
        """
        if self.loading_label:
            import time
            self.loading_label.config(text=message)

            # Throttle GUI updates to every 100ms to avoid slowdown on Windows localhost
            current_time = time.time()
            if force or (current_time - self.last_gui_update) >= 0.1:
                self.dialog.update_idletasks()
                self.last_gui_update = current_time

    def on_service_change(self, new_service: str):
        """
        Handle service type change.

        Args:
            new_service: New service type selected
        """
        self.current_service = new_service
        self.show_loading_indicator()
        self.dialog.after(100, self.load_files)

    def load_files(self):
        """Load list of files with revision counts from server."""
        # Update loading indicator (force immediate update)
        self.update_loading_indicator("Loading files...", force=True)

        # Clear current data
        self.file_listbox.delete(0, tk.END)
        self.files_data = []
        self.selected_file = None
        self.clear_revisions()

        if not self.api:
            self.hide_loading_indicator()
            messagebox.showerror("Not Logged In",
                                "You must be logged in to view revision history.",
                                parent=self.dialog)
            return

        if not self.current_service:
            self.hide_loading_indicator()
            messagebox.showerror("No Service Selected",
                                "Please select a service type.",
                                parent=self.dialog)
            return

        try:
            # Get file list from server
            self.update_loading_indicator("Fetching file list from server...", force=True)
            files = self.api.list_files(self.current_service)

            if not files:
                self.hide_loading_indicator()
                self.file_listbox.insert(tk.END, "(No files found)")
                return

            # Sort files alphabetically by path
            files = sorted(files, key=lambda f: f['path'].lower())

            total_files = len(files)

            # For each file, get revision count
            for index, file_info in enumerate(files, 1):
                path = file_info['path']

                # Update progress
                self.update_loading_indicator(f"Loading file {index} of {total_files}...")

                # Get revisions for this file
                try:
                    revisions = self.api.get_file_revisions(path, self.current_service)
                    revision_count = len(revisions)

                    # Store file data including all revisions for later use
                    self.files_data.append({
                        'path': path,
                        'revision_count': revision_count,
                        'revisions': revisions  # Cache revision data to avoid duplicate API calls
                    })

                    # Add to listbox (show files with multiple revisions first)
                    display_text = f"{path} [{revisions[0]['revision']}]"
                    self.file_listbox.insert(tk.END, display_text)

                except Exception as e:
                    # If we can't get revisions for a file, skip it
                    continue

            if self.file_listbox.size() == 0:
                self.file_listbox.insert(tk.END, "(No files with revisions found)")

            # Hide loading indicator when done
            self.hide_loading_indicator()

        except AlderSyncAuthError as e:
            self.hide_loading_indicator()
            messagebox.showerror("Authentication Error",
                                f"Failed to load files:\n\n{e}",
                                parent=self.dialog)
        except AlderSyncServerError as e:
            self.hide_loading_indicator()
            messagebox.showerror("Server Error",
                                f"Failed to load files:\n\n{e}",
                                parent=self.dialog)

    def on_file_select(self, event):
        """
        Handle file selection in listbox.

        Args:
            event: Tkinter event
        """
        selection = self.file_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index >= len(self.files_data):
            return

        # Get selected file
        file_data = self.files_data[index]
        self.selected_file = file_data['path']

        # Update label
        self.selected_file_label.config(text=f"File: {self.selected_file}",
                                        font=("Arial", 9), foreground="black")

        # Load revisions for this file
        self.load_revisions()

    def load_revisions(self):
        """Load revisions for the selected file."""
        if not self.selected_file:
            return

        # Clear current revisions
        self.clear_revisions()

        try:
            # Get cached revisions from files_data (already fetched during load_files)
            # Find the file in files_data
            file_data = None
            for fd in self.files_data:
                if fd['path'] == self.selected_file:
                    file_data = fd
                    break

            if not file_data or 'revisions' not in file_data:
                # Fallback: fetch from server if not cached (shouldn't happen in normal flow)
                revisions = self.api.get_file_revisions(self.selected_file, self.current_service)
            else:
                # Use cached data - no need for duplicate API call
                revisions = file_data['revisions']

            self.revisions_data = revisions

            # Find the highest revision number (current version)
            max_revision = max([r['revision'] for r in revisions]) if revisions else 0

            # Populate tree view
            for rev in revisions:
                revision_num = rev['revision']
                size = rev['size']
                modified = rev['modified_utc']
                username = rev.get('username')
                changelist_id = rev.get('changelist_id')

                # Format values
                revision_display = f"#{revision_num}"
                # Mark the highest revision as current
                if revision_num == max_revision:
                    revision_display = f"#{revision_num} (Current)"

                size_display = self.format_size(size) if size else "N/A"
                modified_display = self.format_datetime(modified) if modified else "N/A"
                username_display = username if username else "Unknown"
                changelist_display = str(changelist_id) if changelist_id is not None else "N/A"

                # Insert into tree
                self.revision_tree.insert("", tk.END, values=(
                    revision_display,
                    size_display,
                    modified_display,
                    username_display,
                    changelist_display
                ))

            # Enable buttons if there are revisions
            if len(revisions) > 0:
                self.save_as_btn.config(state=tk.NORMAL)
                self.pull_btn.config(state=tk.NORMAL)
            else:
                self.save_as_btn.config(state=tk.DISABLED)
                self.pull_btn.config(state=tk.DISABLED)

            # Enable restore button if there are old revisions
            if len(revisions) > 1:
                self.restore_btn.config(state=tk.NORMAL)
            else:
                self.restore_btn.config(state=tk.DISABLED)

        except AlderSyncAuthError as e:
            messagebox.showerror("Authentication Error",
                                f"Failed to load revisions:\n\n{e}",
                                parent=self.dialog)
        except AlderSyncServerError as e:
            messagebox.showerror("Server Error",
                                f"Failed to load revisions:\n\n{e}",
                                parent=self.dialog)

    def clear_revisions(self):
        """Clear revision tree view."""
        for item in self.revision_tree.get_children():
            self.revision_tree.delete(item)
        self.save_as_btn.config(state=tk.DISABLED)
        self.pull_btn.config(state=tk.DISABLED)
        self.restore_btn.config(state=tk.DISABLED)

    def save_as_revision(self):
        """Save the selected revision to a custom file location."""
        # Get selected revision
        selection = self.revision_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                                  "Please select a revision to save.",
                                  parent=self.dialog)
            return

        # Get selected item index
        item = selection[0]
        item_index = self.revision_tree.index(item)

        # Get the corresponding revision data
        if item_index >= len(self.revisions_data):
            messagebox.showerror("Error",
                                "Could not find revision data.",
                                parent=self.dialog)
            return

        rev_data = self.revisions_data[item_index]
        revision_num = rev_data['revision']

        # Get default filename (use the original filename from the path)
        default_filename = os.path.basename(self.selected_file)

        # Add revision number to filename for clarity (unless it's current version)
        if revision_num > 0:
            name, ext = os.path.splitext(default_filename)
            default_filename = f"{name}.{revision_num}{ext}"

        # Ask user where to save the file
        save_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title=f"Save Revision #{revision_num}",
            initialfile=default_filename,
            defaultextension=os.path.splitext(default_filename)[1],
            filetypes=[
                ("All Files", "*.*"),
                ("ProPresenter Files", "*.pro*"),
                ("Text Files", "*.txt"),
            ]
        )

        if not save_path:
            # User cancelled
            return

        try:
            # Download revision from server
            file_data = self.api.download_file_revision(
                self.selected_file,
                revision_num,
                self.current_service
            )

            # Write to file
            with open(save_path, 'wb') as f:
                f.write(file_data)

            messagebox.showinfo(
                "Download Successful",
                f"Revision #{revision_num} has been downloaded successfully.\n\n"
                f"Saved to: {save_path}",
                parent=self.dialog
            )

        except AlderSyncAuthError as e:
            messagebox.showerror("Authentication Error",
                                f"Failed to download revision:\n\n{e}",
                                parent=self.dialog)
        except AlderSyncServerError as e:
            messagebox.showerror("Server Error",
                                f"Failed to download revision:\n\n{e}",
                                parent=self.dialog)
        except IOError as e:
            messagebox.showerror("File Error",
                                f"Failed to write file:\n\n{e}",
                                parent=self.dialog)

    def pull_revision(self):
        """Pull the selected revision to its intended ProPresenter location."""
        # Get selected revision
        selection = self.revision_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                                  "Please select a revision to pull.",
                                  parent=self.dialog)
            return

        # Get selected item index
        item = selection[0]
        item_index = self.revision_tree.index(item)

        # Get the corresponding revision data
        if item_index >= len(self.revisions_data):
            messagebox.showerror("Error",
                                "Could not find revision data.",
                                parent=self.dialog)
            return

        rev_data = self.revisions_data[item_index]
        revision_num = rev_data['revision']
        revision_hash = rev_data.get('hash')
        revision_size = rev_data.get('size', 0)

        # Get the target path in ProPresenter folder
        folder_mgr = FolderManager(self.config_mgr.get("documents_path"))
        propresenter_path = folder_mgr.propresenter_folder

        if not propresenter_path.exists():
            messagebox.showerror("ProPresenter Folder Not Found",
                                f"Could not find ProPresenter folder.\n\n"
                                f"Expected location: {propresenter_path}",
                                parent=self.dialog)
            return

        # Build target file path
        target_path = str(propresenter_path / self.selected_file)

        # Ensure parent directory exists
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Directory Error",
                                    f"Failed to create directory:\n\n{e}",
                                    parent=self.dialog)
                return

        # Check if file already exists at target
        file_exists = os.path.exists(target_path)
        should_backup = False
        backup_path = None

        if file_exists:
            # Calculate hash of existing file
            try:
                with open(target_path, 'rb') as f:
                    existing_hash = hashlib.sha256(f.read()).hexdigest()
                existing_size = os.path.getsize(target_path)
            except Exception as e:
                messagebox.showerror("File Read Error",
                                    f"Failed to read existing file:\n\n{e}",
                                    parent=self.dialog)
                return

            # Check if existing file matches any revision
            matches_revision = False
            for rev in self.revisions_data:
                if rev.get('hash') == existing_hash:
                    matches_revision = True
                    break

            # Determine if we need to ask for confirmation
            need_confirmation = False
            offer_backup = False

            if not matches_revision:
                # File doesn't match any revision - always ask and offer backup
                need_confirmation = True
                offer_backup = True
            else:
                # File matches a revision - only ask if above size threshold
                size_threshold_mb = self.config_mgr.get("pull_confirmation_size_mb", 100)
                size_threshold_bytes = size_threshold_mb * 1024 * 1024

                if revision_size > size_threshold_bytes:
                    need_confirmation = True
                    offer_backup = False

            if need_confirmation:
                # Build confirmation message
                if offer_backup:
                    msg = (f"The file already exists and has been modified locally.\n\n"
                           f"File: {os.path.basename(target_path)}\n"
                           f"Current size: {self.format_size(existing_size)}\n"
                           f"Revision size: {self.format_size(revision_size)}\n\n"
                           f"Would you like to backup your current version before pulling?")

                    # Ask if they want to backup
                    response = messagebox.askyesnocancel(
                        "Backup Existing File?",
                        msg,
                        parent=self.dialog
                    )

                    if response is None:  # Cancel
                        return
                    elif response:  # Yes - backup
                        should_backup = True
                    # else: No - don't backup, just overwrite

                else:
                    # File matches a revision but is large
                    msg = (f"Are you sure you want to pull this revision?\n\n"
                           f"File: {os.path.basename(target_path)}\n"
                           f"Size: {self.format_size(revision_size)}\n\n"
                           f"The file already exists and will be replaced.")

                    confirm = messagebox.askyesno(
                        "Confirm Pull",
                        msg,
                        parent=self.dialog
                    )

                    if not confirm:
                        return

            # If backup requested, ask where to save it
            if should_backup:
                default_backup_name = f"{os.path.splitext(os.path.basename(target_path))[0]}_backup{os.path.splitext(target_path)[1]}"

                backup_path = filedialog.asksaveasfilename(
                    parent=self.dialog,
                    title="Save Backup As",
                    initialfile=default_backup_name,
                    defaultextension=os.path.splitext(target_path)[1],
                    filetypes=[
                        ("All Files", "*.*"),
                        ("ProPresenter Files", "*.pro*"),
                        ("Text Files", "*.txt"),
                    ]
                )

                if not backup_path:
                    # User cancelled backup
                    return

                # Backup existing file
                try:
                    import shutil
                    shutil.copy2(target_path, backup_path)
                except Exception as e:
                    messagebox.showerror("Backup Error",
                                        f"Failed to backup existing file:\n\n{e}",
                                        parent=self.dialog)
                    return

        # Download revision from server
        try:
            file_data = self.api.download_file_revision(
                self.selected_file,
                revision_num,
                self.current_service
            )

            # Write to target location
            with open(target_path, 'wb') as f:
                f.write(file_data)

            # Set file modified time to match server's recorded time
            modified_utc = rev_data.get('modified_utc')
            if modified_utc:
                try:
                    # Parse ISO format datetime string
                    if modified_utc.endswith('Z'):
                        modified_utc = modified_utc[:-1] + '+00:00'
                    dt = datetime.fromisoformat(modified_utc)
                    # Convert to timestamp
                    timestamp = dt.timestamp()
                    # Set both access time and modification time
                    os.utime(target_path, (timestamp, timestamp))
                except Exception as e:
                    # Log but don't fail if timestamp setting fails
                    logger.warning(f"Failed to set file timestamp: {e}")

            # Build success message
            success_msg = f"Revision #{revision_num} has been pulled successfully.\n\n"
            success_msg += f"Saved to: {target_path}"

            if backup_path:
                success_msg += f"\n\nBackup saved to: {backup_path}"

            messagebox.showinfo(
                "Pull Successful",
                success_msg,
                parent=self.dialog
            )

        except AlderSyncAuthError as e:
            messagebox.showerror("Authentication Error",
                                f"Failed to pull revision:\n\n{e}",
                                parent=self.dialog)
        except AlderSyncServerError as e:
            messagebox.showerror("Server Error",
                                f"Failed to pull revision:\n\n{e}",
                                parent=self.dialog)
        except IOError as e:
            messagebox.showerror("File Error",
                                f"Failed to write file:\n\n{e}",
                                parent=self.dialog)

    def restore_revision(self):
        """Restore the selected revision and download it to local ProPresenter folder."""
        # Get selected revision
        selection = self.revision_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                                  "Please select a revision to restore.",
                                  parent=self.dialog)
            return

        # Get selected item index
        item = selection[0]
        item_index = self.revision_tree.index(item)

        # Get the corresponding revision data
        if item_index >= len(self.revisions_data):
            messagebox.showerror("Error",
                                "Could not find revision data.",
                                parent=self.dialog)
            return

        rev_data = self.revisions_data[item_index]
        revision_num = rev_data['revision']
        revision_size = rev_data.get('size', 0)

        # Find the highest revision number (current version)
        max_revision = max([r['revision'] for r in self.revisions_data]) if self.revisions_data else 0

        # Don't allow restoring current version
        if revision_num == max_revision:
            messagebox.showwarning("Invalid Selection",
                                  f"Revision #{revision_num} is already the current version.",
                                  parent=self.dialog)
            return

        # Confirm restoration
        confirm = messagebox.askyesno(
            "Confirm Restoration",
            f"Are you sure you want to restore revision #{revision_num}?\n\n"
            f"File: {self.selected_file}\n"
            f"Service: {self.current_service}\n\n"
            f"This will:\n"
            f"1. Archive the current version on the server\n"
            f"2. Make revision #{revision_num} the new current version\n"
            f"3. Download the restored file to your ProPresenter folder",
            parent=self.dialog
        )

        if not confirm:
            return

        try:
            # Step 1: Restore revision on server
            success = self.api.restore_revision(
                self.selected_file,
                revision_num,
                self.current_service
            )

            if not success:
                messagebox.showerror(
                    "Restoration Failed",
                    "Failed to restore revision on server. Please try again.",
                    parent=self.dialog
                )
                return

            logger.info(f"Successfully restored revision #{revision_num} on server for {self.selected_file}")

            # Step 2: Download the restored file to local ProPresenter folder
            # Get the target path in ProPresenter folder
            folder_mgr = FolderManager(self.config_mgr.get("documents_path"))
            propresenter_path = folder_mgr.propresenter_folder

            if not propresenter_path.exists():
                messagebox.showerror("ProPresenter Folder Not Found",
                                    f"Could not find ProPresenter folder.\n\n"
                                    f"Expected location: {propresenter_path}",
                                    parent=self.dialog)
                return

            # Build target file path
            target_path = str(propresenter_path / self.selected_file)

            # Ensure parent directory exists
            target_dir = os.path.dirname(target_path)
            if target_dir and not os.path.exists(target_dir):
                try:
                    os.makedirs(target_dir, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Directory Error",
                                        f"Failed to create directory:\n\n{e}",
                                        parent=self.dialog)
                    return

            # Check if file already exists and offer backup
            backup_path = None
            if os.path.exists(target_path):
                try:
                    existing_size = os.path.getsize(target_path)
                except Exception as e:
                    messagebox.showerror("File Read Error",
                                        f"Failed to read existing file:\n\n{e}",
                                        parent=self.dialog)
                    return

                # Ask if they want to backup
                msg = (f"A file already exists at this location.\n\n"
                       f"File: {os.path.basename(target_path)}\n"
                       f"Current size: {self.format_size(existing_size)}\n"
                       f"Restored size: {self.format_size(revision_size)}\n\n"
                       f"Would you like to backup your current version before downloading?")

                response = messagebox.askyesnocancel(
                    "Backup Existing File?",
                    msg,
                    parent=self.dialog
                )

                if response is None:  # Cancel
                    return
                elif response:  # Yes - backup
                    default_backup_name = f"{os.path.splitext(os.path.basename(target_path))[0]}_backup{os.path.splitext(target_path)[1]}"

                    backup_path = filedialog.asksaveasfilename(
                        parent=self.dialog,
                        title="Save Backup As",
                        initialfile=default_backup_name,
                        defaultextension=os.path.splitext(target_path)[1],
                        filetypes=[
                            ("All Files", "*.*"),
                            ("ProPresenter Files", "*.pro*"),
                            ("Text Files", "*.txt"),
                        ]
                    )

                    if not backup_path:
                        # User cancelled backup
                        return

                    # Backup existing file
                    try:
                        import shutil
                        shutil.copy2(target_path, backup_path)
                    except Exception as e:
                        messagebox.showerror("Backup Error",
                                            f"Failed to backup existing file:\n\n{e}",
                                            parent=self.dialog)
                        return

            # Download the current version (which is now the restored content)
            # After restore, the server creates a new highest revision with the old content
            # We need to download the current version
            try:
                file_data = self.api.download_file(
                    self.selected_file,
                    self.current_service
                )

                # Write to target location
                with open(target_path, 'wb') as f:
                    f.write(file_data)

                logger.info(f"Downloaded restored file to {target_path}")

                # Build success message
                success_msg = f"Revision #{revision_num} has been restored successfully.\n\n"
                success_msg += f"Downloaded to: {target_path}"

                if backup_path:
                    success_msg += f"\n\nBackup saved to: {backup_path}"

                messagebox.showinfo(
                    "Restoration Successful",
                    success_msg,
                    parent=self.dialog
                )

                # Reload revisions to show updated state
                self.load_revisions()

            except Exception as e:
                messagebox.showerror("Download Error",
                                    f"Revision was restored on server but failed to download:\n\n{e}\n\n"
                                    f"Run a Pull operation to download the restored file.",
                                    parent=self.dialog)

        except AlderSyncAuthError as e:
            messagebox.showerror("Authentication Error",
                                f"Failed to restore revision:\n\n{e}",
                                parent=self.dialog)
        except AlderSyncServerError as e:
            messagebox.showerror("Server Error",
                                f"Failed to restore revision:\n\n{e}",
                                parent=self.dialog)

    @staticmethod
    def format_size(size_bytes):
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 KB", "2.3 MB")
        """
        if size_bytes is None:
            return "N/A"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    @staticmethod
    def format_datetime(dt_string):
        """
        Format datetime string for display in local timezone.

        Args:
            dt_string: ISO format datetime string (in UTC)

        Returns:
            Formatted datetime string in local timezone
        """
        if not dt_string:
            return "N/A"

        try:
            # Parse UTC datetime
            dt_utc = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            # Convert to local timezone
            dt_local = dt_utc.astimezone()
            # Format in local time
            return dt_local.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return dt_string
