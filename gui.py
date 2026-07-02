"""
Receipt Scanner GUI
-------------------
Run this file instead of main.py for a graphical interface.
Settings are saved automatically so they only need to be entered once.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
from dotenv import load_dotenv, set_key

# Import the core processing and email functions from main.py
from main import process_receipt, send_receipt_email, SUPPORTED_EXTENSIONS

ENV_FILE = Path(".env")

# --- Load saved settings from .env if it exists ---
load_dotenv()


class ReceiptApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Receipt Scanner")
        self.geometry("600x580")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")

        # --- Build the two-tab layout ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.run_tab = ttk.Frame(notebook)
        self.settings_tab = ttk.Frame(notebook)

        notebook.add(self.run_tab, text="  Run  ")
        notebook.add(self.settings_tab, text="  Settings  ")

        self._build_run_tab()
        self._build_settings_tab()

    # ------------------------------------------------------------------ #
    #  RUN TAB                                                             #
    # ------------------------------------------------------------------ #

    def _build_run_tab(self):
        frame = self.run_tab
        frame.configure(padding=15)

        # --- Folder picker ---
        folder_frame = ttk.LabelFrame(frame, text="Input Folder", padding=10)
        folder_frame.pack(fill="x", pady=(0, 10))

        self.folder_var = tk.StringVar(value=str(Path("input").resolve()))

        ttk.Entry(folder_frame, textvariable=self.folder_var, width=55).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(folder_frame, text="Browse…", command=self._pick_folder).pack(
            side="left"
        )

        # --- Options ---
        options_frame = ttk.LabelFrame(frame, text="Options", padding=10)
        options_frame.pack(fill="x", pady=(0, 10))

        self.send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Send each PDF by email after processing",
            variable=self.send_email_var,
        ).pack(anchor="w")

        # --- Run button ---
        self.run_btn = ttk.Button(
            frame, text="Start Processing", command=self._start_processing
        )
        self.run_btn.pack(fill="x", pady=(0, 10))

        # --- Progress bar ---
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))

        self.progress_label = ttk.Label(frame, text="Ready", foreground="#555")
        self.progress_label.pack(anchor="w", pady=(0, 6))

        # --- Log ---
        log_frame = ttk.LabelFrame(frame, text="Log", padding=6)
        log_frame.pack(fill="both", expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame, height=12, state="disabled",
            font=("Courier", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", relief="flat"
        )
        self.log.pack(fill="both", expand=True)

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select input folder")
        if folder:
            self.folder_var.set(folder)

    def _log(self, message: str, colour: str = "#d4d4d4"):
        """Append a line to the log widget from any thread."""
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start_processing(self):
        """Validate settings then kick off processing in a background thread."""
        # Check settings are filled in
        required = ["SENDER_EMAIL", "SENDER_PASSWORD", "RECIPIENT_EMAIL", "EMAIL_PROVIDER"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing and self.send_email_var.get():
            messagebox.showwarning(
                "Missing settings",
                f"Please fill in the Settings tab before sending emails.\n\nMissing: {', '.join(missing)}"
            )
            return

        input_dir = Path(self.folder_var.get())
        if not input_dir.exists():
            messagebox.showerror("Folder not found", f"Could not find folder:\n{input_dir}")
            return

        # Disable the run button while processing
        self.run_btn.configure(state="disabled", text="Processing…")
        self.progress_var.set(0)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        # Run in background so the UI doesn't freeze
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(input_dir, self.send_email_var.get()),
            daemon=True
        )
        thread.start()

    def _run_pipeline(self, input_dir: Path, send_emails: bool):
        """The actual processing loop - runs in a background thread."""
        output_dir = Path("output")
        failed_dir = Path("failed")
        output_dir.mkdir(exist_ok=True)
        failed_dir.mkdir(exist_ok=True)

        # Collect files to process
        files = [
            f for f in sorted(input_dir.iterdir())
            if f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        if not files:
            self._log("No supported image files found in the selected folder.", "#f1c40f")
            self._done(0, 0, 0, 0)
            return

        total = len(files)
        processed = failed = emailed = email_failed = 0

        for i, file_path in enumerate(files):
            self._log(f"\nProcessing: {file_path.name}")
            self.progress_label.configure(text=f"Processing {i + 1} of {total}: {file_path.name}")

            try:
                output_path = process_receipt(file_path)
                self._log(f"  ✓ Saved: {output_path.name}", "#4ec9b0")
                processed += 1

                if send_emails:
                    try:
                        send_receipt_email(output_path)
                        self._log(f"  ✓ Emailed: {output_path.name}", "#4ec9b0")
                        emailed += 1
                    except Exception as email_err:
                        self._log(f"  ✗ Email failed: {email_err}", "#f44747")
                        email_failed += 1

            except Exception as err:
                self._log(f"  ✗ Failed: {err}", "#f44747")
                failed += 1
                failed_path = failed_dir / file_path.name
                file_path.rename(failed_path)

            # Update progress bar
            self.progress_var.set((i + 1) / total * 100)

        self._done(processed, failed, emailed, email_failed)

    def _done(self, processed, failed, emailed, email_failed):
        """Called when the pipeline finishes — re-enables the UI."""
        self._log(
            f"\n— Done — Processed: {processed}, Failed: {failed}, "
            f"Emailed: {emailed}, Email failures: {email_failed}",
            "#569cd6"
        )
        self.progress_label.configure(
            text=f"Done — {processed} processed, {failed} failed"
        )
        self.run_btn.configure(state="normal", text="Start Processing")

    # ------------------------------------------------------------------ #
    #  SETTINGS TAB                                                        #
    # ------------------------------------------------------------------ #

    def _build_settings_tab(self):
        frame = self.settings_tab
        frame.configure(padding=20)

        ttk.Label(
            frame,
            text="These settings are saved automatically and only need to be entered once.",
            foreground="#555", wraplength=520
        ).pack(anchor="w", pady=(0, 15))

        # --- Email provider ---
        provider_frame = ttk.LabelFrame(frame, text="Email Provider", padding=10)
        provider_frame.pack(fill="x", pady=(0, 10))

        self.provider_var = tk.StringVar(
            value=os.environ.get("EMAIL_PROVIDER", "gmail")
        )
        ttk.Radiobutton(
            provider_frame, text="Gmail", variable=self.provider_var, value="gmail"
        ).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(
            provider_frame, text="Outlook", variable=self.provider_var, value="outlook"
        ).pack(side="left")

        # --- Credentials ---
        creds_frame = ttk.LabelFrame(frame, text="Credentials", padding=10)
        creds_frame.pack(fill="x", pady=(0, 10))

        fields = [
            ("Sender email address", "SENDER_EMAIL", False),
            ("Password / App Password", "SENDER_PASSWORD", True),
            ("Recipient email address", "RECIPIENT_EMAIL", False),
        ]

        self.setting_vars = {}
        for label, key, secret in fields:
            row = ttk.Frame(creds_frame)
            row.pack(fill="x", pady=4)

            ttk.Label(row, text=label, width=26, anchor="w").pack(side="left")
            var = tk.StringVar(value=os.environ.get(key, ""))
            self.setting_vars[key] = var

            ttk.Entry(
                row, textvariable=var, width=34,
                show="●" if secret else ""
            ).pack(side="left")

        # --- Gmail note ---
        note = ttk.Label(
            frame,
            text="Gmail users: your password must be an App Password, not your normal Gmail password.\n"
                 "Generate one at: Google Account → Security → App Passwords\n"
                 "(requires 2-Step Verification to be turned on first)",
            foreground="#888", wraplength=520, font=("TkDefaultFont", 9)
        )
        note.pack(anchor="w", pady=(0, 15))

        # --- Save button ---
        ttk.Button(frame, text="Save Settings", command=self._save_settings).pack(
            anchor="w"
        )

        self.save_status = ttk.Label(frame, text="", foreground="#4ec9b0")
        self.save_status.pack(anchor="w", pady=(6, 0))

    def _save_settings(self):
        """Write all settings to the .env file and reload them into os.environ."""
        # Make sure the .env file exists
        if not ENV_FILE.exists():
            ENV_FILE.touch()

        set_key(str(ENV_FILE), "EMAIL_PROVIDER", self.provider_var.get())
        os.environ["EMAIL_PROVIDER"] = self.provider_var.get()

        for key, var in self.setting_vars.items():
            set_key(str(ENV_FILE), key, var.get())
            os.environ[key] = var.get()

        self.save_status.configure(text="✓ Settings saved")
        # Clear the confirmation message after 3 seconds
        self.after(3000, lambda: self.save_status.configure(text=""))


if __name__ == "__main__":
    app = ReceiptApp()
    app.mainloop()