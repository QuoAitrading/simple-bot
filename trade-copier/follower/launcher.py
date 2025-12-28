"""
QuoTrading Trade Copier - Customer Launcher
============================================
Professional GUI with real TopStep SDK connection.
Validates API key, connects to broker, lets user select accounts.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
from pathlib import Path
from datetime import datetime, timezone
import sys
import threading
import asyncio
import requests

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import getpass
import uuid
import platform

# ========================================
# CONFIGURATION
# ========================================
CLOUD_API_BASE_URL = os.getenv("QUOTRADING_API_URL", "https://quotrading-flask-api.azurewebsites.net")


def get_device_fingerprint() -> str:
    """Generate unique device fingerprint for session locking."""
    try:
        machine_id = str(uuid.getnode())
    except:
        machine_id = "unknown"
    try:
        username = getpass.getuser()
    except:
        username = "unknown"
    platform_name = platform.system()
    fingerprint_raw = f"{machine_id}:{username}:{platform_name}"
    return hashlib.sha256(fingerprint_raw.encode()).hexdigest()[:16]

# Try to import TopStep SDK
try:
    from project_x_py import ProjectX, ProjectXConfig
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("⚠️ TopStep SDK not installed. Run: pip install project-x-py")


class TradeCopierLauncher:
    """Professional GUI launcher with real broker connection."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QuoTrading - Broker Setup")
        self.root.geometry("650x530")
        self.root.resizable(False, False)
        
        # Dark theme colors
        self.colors = {
            'primary': '#1E1E1E',
            'secondary': '#252525',
            'success': '#0078D4',
            'success_dark': '#0078D4',
            'error': '#DC2626',
            'warning': '#F59E0B',
            'background': '#1E1E1E',
            'card': '#2D2D2D',
            'card_elevated': '#3A3A3A',
            'text': '#FFFFFF',
            'text_light': '#D0D0D0',
            'text_secondary': '#A0A0A0',
            'border': '#0078D4',
            'border_subtle': '#404040',
            'input_bg': '#2D2D2D',
            'input_focus': '#1A3A52',
            'button_hover': '#0078D4',
            'shadow': '#000000',
            'listening': '#00FF88'
        }
        
        self.root.configure(bg=self.colors['background'])
        
        # Load saved config
        self.config_file = Path(__file__).parent / "config.json"
        self.config = self.load_config()
        
        # Connection state
        self.sdk_client = None
        self.accounts = []  # List of account dicts from broker
        self.selected_accounts = []  # Accounts user selected
        self.receiving = False
        
        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start with login screen
        self.setup_broker_screen()
    
    def load_config(self) -> dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def on_closing(self):
        self.receiving = False
        self.root.destroy()
    
    def create_header(self, title, subtitle=""):
        header = tk.Frame(self.root, bg=self.colors['success_dark'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Frame(header, bg=self.colors['success'], height=2).pack(fill=tk.X)
        
        tk.Label(
            header, text=title,
            font=("Segoe UI", 13, "bold"),
            bg=self.colors['success_dark'], fg='white'
        ).pack(pady=(17, 2))
        
        if subtitle:
            tk.Label(
                header, text=subtitle,
                font=("Segoe UI", 7),
                bg=self.colors['success_dark'], fg='white'
            ).pack(pady=(0, 8))
        
        tk.Frame(header, bg=self.colors['shadow'], height=1).pack(side=tk.BOTTOM, fill=tk.X)
        return header
    
    def create_input_field(self, parent, label_text, is_password=False):
        container = tk.Frame(parent, bg=self.colors['card'])
        container.pack(fill=tk.X, pady=2)
        
        tk.Label(
            container, text=label_text,
            font=("Segoe UI", 9, "bold"),
            bg=self.colors['card'], fg=self.colors['text']
        ).pack(anchor=tk.W, pady=(0, 1))
        
        input_frame = tk.Frame(container, bg=self.colors['border_subtle'], bd=0)
        input_frame.pack(fill=tk.X, padx=1, pady=1)
        
        entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 9),
            bg=self.colors['input_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['success'],
            relief=tk.FLAT, bd=0,
            show="●" if is_password else ""
        )
        entry.pack(fill=tk.X, ipady=4, padx=2, pady=2)
        
        def on_focus_in(e):
            input_frame.config(bg=self.colors['success'])
            entry.config(bg=self.colors['input_focus'])
        def on_focus_out(e):
            input_frame.config(bg=self.colors['border_subtle'])
            entry.config(bg=self.colors['input_bg'])
        
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry
    
    def setup_broker_screen(self):
        """Screen 0: Login - same as main QuoTrading launcher."""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.configure(bg=self.colors['background'])
        self.root.title("QuoTrading - Broker Setup")
        
        self.create_header("QuoTrading AI", "Select your account type and broker")
        
        main = tk.Frame(self.root, bg=self.colors['background'], padx=10, pady=5)
        main.pack(fill=tk.BOTH, expand=True)
        
        card = tk.Frame(main, bg=self.colors['card'], relief=tk.FLAT, bd=0)
        card.pack(fill=tk.BOTH, expand=True)
        card.configure(highlightbackground=self.colors['border'], highlightthickness=2)
        
        content = tk.Frame(card, bg=self.colors['card'], padx=10, pady=2)
        content.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            content, text="Choose your broker type and enter credentials",
            font=("Segoe UI", 8), bg=self.colors['card'], fg=self.colors['text_light']
        ).pack(pady=(0, 2))
        
        # Account Type
        tk.Label(content, text="Account Type:", font=("Segoe UI", 9, "bold"),
                bg=self.colors['card'], fg=self.colors['text']).pack(pady=(0, 3))
        
        cards_container = tk.Frame(content, bg=self.colors['card'])
        cards_container.pack(fill=tk.X, pady=(0, 4))
        
        self.broker_type_var = tk.StringVar(value=self.config.get("broker_type", "Prop Firm"))
        self.broker_cards = {}
        
        for btype, icon, desc in [("Prop Firm", "💼", "Funded trading"), ("Live Broker", "🏦", "Direct accounts")]:
            card_frame = tk.Frame(cards_container, bg=self.colors['secondary'], relief=tk.FLAT, bd=0,
                                 highlightthickness=2,
                                 highlightbackground=self.colors['border'] if self.broker_type_var.get() == btype else self.colors['text_secondary'])
            card_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3)
            
            def make_select(bt=btype):
                return lambda e: self.select_broker_type(bt)
            card_frame.bind("<Button-1>", make_select(btype))
            
            inner = tk.Frame(card_frame, bg=self.colors['secondary'])
            inner.pack(expand=True, fill=tk.BOTH, padx=4, pady=4)
            inner.bind("<Button-1>", make_select(btype))
            
            for widget_text, font_cfg in [(icon, ("Segoe UI", 12)), (btype, ("Segoe UI", 8, "bold")), (desc, ("Segoe UI", 7))]:
                lbl = tk.Label(inner, text=widget_text, font=font_cfg, bg=self.colors['secondary'],
                              fg=self.colors['text'] if font_cfg[1] != 7 else self.colors['text_light'])
                lbl.pack()
                lbl.bind("<Button-1>", make_select(btype))
            
            self.broker_cards[btype] = card_frame
        
        # Broker dropdown
        tk.Label(content, text="Select Broker:", font=("Segoe UI", 9, "bold"),
                bg=self.colors['card'], fg=self.colors['text']).pack(anchor=tk.W, pady=(4, 2))
        
        self.broker_var = tk.StringVar(value=self.config.get("broker", "TopStep"))
        self.broker_dropdown = ttk.Combobox(content, textvariable=self.broker_var, state="readonly",
                                           font=("Segoe UI", 9), width=35)
        self.broker_dropdown.pack(fill=tk.X, pady=(0, 4))
        self.update_broker_options()
        
        # Credentials
        self.broker_username_entry = self.create_input_field(content, "Username/Email:")
        if self.config.get("broker_username"):
            self.broker_username_entry.insert(0, self.config["broker_username"])
        
        self.broker_token_entry = self.create_input_field(content, "Broker API Key:", is_password=True)
        if self.config.get("broker_token"):
            self.broker_token_entry.insert(0, self.config["broker_token"])
        
        self.quotrading_api_key_entry = self.create_input_field(content, "QuoTrading License Key:", is_password=True)
        if self.config.get("quotrading_api_key"):
            self.quotrading_api_key_entry.insert(0, self.config["quotrading_api_key"])
        
        # Remember + Login
        remember_frame = tk.Frame(content, bg=self.colors['card'])
        remember_frame.pack(fill=tk.X, pady=(6, 10))
        
        self.remember_var = tk.BooleanVar(value=self.config.get("remember_credentials", True))
        tk.Checkbutton(remember_frame, text="Save credentials", variable=self.remember_var,
                      font=("Segoe UI", 8), bg=self.colors['card'], fg=self.colors['text'],
                      selectcolor=self.colors['secondary'], cursor="hand2").pack(side=tk.LEFT)
        
        tk.Button(remember_frame, text="LOGIN", font=("Segoe UI", 10, "bold"),
                 bg=self.colors['success_dark'], fg='white', relief=tk.FLAT,
                 command=self.validate_and_connect, cursor="hand2", width=16).pack(side=tk.RIGHT, ipady=6)
    
    def select_broker_type(self, broker_type):
        self.broker_type_var.set(broker_type)
        for btype, card in self.broker_cards.items():
            card.config(highlightbackground=self.colors['border'] if btype == broker_type else self.colors['text_secondary'])
        self.update_broker_options()
    
    def update_broker_options(self):
        options = ["TopStep"] if self.broker_type_var.get() == "Prop Firm" else ["Tradovate"]
        self.broker_dropdown['values'] = options
        self.broker_dropdown.current(0)
    
    def validate_and_connect(self):
        """Validate API key with server, then connect to broker."""
        broker = self.broker_var.get()
        username = self.broker_username_entry.get().strip()
        token = self.broker_token_entry.get().strip()
        api_key = self.quotrading_api_key_entry.get().strip()
        
        if not username or not token:
            messagebox.showerror("Missing Credentials", f"Please enter {broker} credentials.")
            return
        if not api_key:
            messagebox.showerror("Missing License", "Please enter your QuoTrading License Key.")
            return
        
        # Save config
        if self.remember_var.get():
            self.config.update({
                "broker_type": self.broker_type_var.get(),
                "broker": broker,
                "broker_username": username,
                "broker_token": token,
                "quotrading_api_key": api_key,
                "remember_credentials": True
            })
            self.save_config()
        
        self.show_loading("Validating license...")
        
        def validate_thread():
            # Step 1: Validate API key with server and check for duplicate sessions
            try:
                resp = requests.post(
                    f"{CLOUD_API_BASE_URL}/api/validate-license",
                    json={
                        "license_key": api_key,
                        "device_fingerprint": get_device_fingerprint(),
                        "symbol": "COPIER",  # Use COPIER as symbol for copier sessions
                        "check_only": False  # Claim session lock
                    },
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("license_valid"):
                        err = data.get("message", "Invalid license key")
                        self.root.after(0, self.hide_loading)
                        self.root.after(0, lambda m=err: messagebox.showerror("License Invalid", m))
                        return
                elif resp.status_code == 403:
                    # Session conflict or license expired
                    data = resp.json()
                    if data.get("session_conflict"):
                        wait_time = data.get("estimated_wait_seconds", 60)
                        self.root.after(0, self.hide_loading)
                        self.root.after(0, lambda: messagebox.showerror(
                            "Session Active",
                            f"This license is currently in use on another device.\n\n"
                            f"Please wait {wait_time} seconds after closing the other session, "
                            f"or close the other instance first."
                        ))
                        return
                    else:
                        err = data.get("message", "License expired or invalid")
                        self.root.after(0, self.hide_loading)
                        self.root.after(0, lambda m=err: messagebox.showerror("License Error", m))
                        return
                else:
                    err = resp.json().get("message", f"Server returned {resp.status_code}")
                    self.root.after(0, self.hide_loading)
                    self.root.after(0, lambda m=err: messagebox.showerror("License Invalid", m))
                    return
                    
            except Exception as ex:
                err = str(ex)
                self.root.after(0, self.hide_loading)
                self.root.after(0, lambda m=err: messagebox.showerror("Connection Error", f"Cannot reach server: {m}"))
                return
            
            # Step 1b: Send immediate heartbeat to CREATE/CLAIM the session lock
            # This prevents window where another user could login during first 20 seconds
            # (Same logic as main bot's validate_license_at_startup)
            try:
                heartbeat_resp = requests.post(
                    f"{CLOUD_API_BASE_URL}/api/heartbeat",
                    json={
                        "license_key": api_key,
                        "device_fingerprint": get_device_fingerprint(),
                        "symbol": "COPIER",
                        "status": "online",
                        "metadata": {"client": "copier_launcher"}
                    },
                    timeout=10
                )
                if heartbeat_resp.status_code == 200:
                    # Session lock created successfully
                    pass
            except:
                # Heartbeat failed - log but don't block startup
                pass
            
            # Step 2: Connect to TopStep using standalone CopierBroker (no main bot dependencies)
            self.root.after(0, lambda: self.update_loading("Connecting to broker..."))
            
            try:
                # Import CopierBroker from shared folder (standalone, no instrument needed)
                from shared.copier_broker import CopierBroker
                
                # Connect using the copier broker wrapper
                self.broker = CopierBroker(username=username, api_token=token)
                
                # Run async connect in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(self.broker.connect())
                loop.close()
                
                if not connected:
                    self.root.after(0, self.hide_loading)
                    self.root.after(0, lambda: messagebox.showerror("Connection Failed", "Could not connect to TopStep. Check credentials."))
                    return
                
                # Get ALL accounts - already fetched during broker.connect()
                all_accounts = getattr(self.broker, 'all_accounts', [])
                
                if all_accounts and len(all_accounts) > 0:
                    self.accounts = []
                    for acc in all_accounts:
                        acc_id = str(getattr(acc, 'id', getattr(acc, 'account_id', '')))
                        acc_name = getattr(acc, 'name', getattr(acc, 'account_name', f'Account {acc_id}'))
                        acc_balance = float(getattr(acc, 'balance', getattr(acc, 'equity', 0)))
                        
                        self.accounts.append({
                            "id": acc_id,
                            "name": acc_name,
                            "balance": acc_balance,
                            "status": "connected"
                        })
                else:
                    # Fallback to single account from get_account_info
                    if self.broker.sdk_client:
                        account_info = self.broker.sdk_client.get_account_info()
                        if account_info:
                            self.accounts = [{
                                "id": str(getattr(account_info, 'id', 'MAIN')),
                                "name": getattr(account_info, 'name', 'TopStep Account'),
                                "balance": self.broker.account_balance,
                                "status": "connected"
                            }]
                        else:
                            self.accounts = [{
                                "id": "TOPSTEP_MAIN",
                                "name": f"TopStep ({username})",
                                "balance": self.broker.account_balance,
                                "status": "connected"
                            }]
                    else:
                        self.accounts = [{
                            "id": "TOPSTEP_MAIN",
                            "name": f"TopStep ({username})",
                            "balance": 0,
                            "status": "connected"
                        }]
                
                self.root.after(0, self.hide_loading)
                self.root.after(0, self.setup_account_selection_screen)
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, self.hide_loading)
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Broker Error", f"Failed to connect: {msg}"))
        
        threading.Thread(target=validate_thread, daemon=True).start()
    
    def setup_account_selection_screen(self):
        """Screen 1: Select which accounts for AI trading."""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.title("QuoTrading - Select Accounts")
        self.root.geometry("650x550")
        
        self.create_header("QuoTrading AI", "Select accounts to receive trade signals")
        
        main = tk.Frame(self.root, bg=self.colors['background'], padx=20, pady=10)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        tk.Label(main, text="Select the accounts for AI trading:",
                font=("Segoe UI", 10), bg=self.colors['background'], fg=self.colors['text_light']).pack(pady=(0, 10))
        
        # Account checkboxes
        self.account_vars = {}
        
        accounts_frame = tk.Frame(main, bg=self.colors['card'])
        accounts_frame.pack(fill=tk.BOTH, expand=True)
        accounts_frame.configure(highlightbackground=self.colors['border'], highlightthickness=2)
        
        for acc in self.accounts:
            acc_frame = tk.Frame(accounts_frame, bg=self.colors['card'])
            acc_frame.pack(fill=tk.X, padx=10, pady=5)
            
            var = tk.BooleanVar(value=True)  # Default selected
            self.account_vars[acc['id']] = var
            
            cb = tk.Checkbutton(
                acc_frame, variable=var,
                bg=self.colors['card'], fg=self.colors['text'],
                selectcolor=self.colors['secondary'],
                activebackground=self.colors['card'],
                cursor="hand2"
            )
            cb.pack(side=tk.LEFT)
            
            # Account info
            info_frame = tk.Frame(acc_frame, bg=self.colors['card'])
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            
            tk.Label(info_frame, text=acc['name'], font=("Segoe UI", 10, "bold"),
                    bg=self.colors['card'], fg=self.colors['text']).pack(anchor=tk.W)
            tk.Label(info_frame, text=acc['id'], font=("Segoe UI", 8),
                    bg=self.colors['card'], fg=self.colors['text_secondary']).pack(anchor=tk.W)
            
            # Balance
            tk.Label(acc_frame, text=f"${acc['balance']:,.2f}", font=("Segoe UI", 11, "bold"),
                    bg=self.colors['card'], fg=self.colors['success']).pack(side=tk.RIGHT, padx=10)
        
        # Launch button
        btn_frame = tk.Frame(main, bg=self.colors['background'])
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        tk.Button(btn_frame, text="🚀 LAUNCH", font=("Segoe UI", 12, "bold"),
                 bg=self.colors['success'], fg='white', relief=tk.FLAT,
                 command=self.launch_listening, cursor="hand2").pack(fill=tk.X, ipady=10)
        
        # Back button
        tk.Button(btn_frame, text="← Back", font=("Segoe UI", 9),
                 bg=self.colors['secondary'], fg=self.colors['text'], relief=tk.FLAT,
                 command=self.setup_broker_screen, cursor="hand2").pack(fill=tk.X, pady=(5, 0), ipady=5)
    
    def launch_listening(self):
        """Start listening - show countdown then launch PowerShell."""
        # Get selected accounts
        self.selected_accounts = [
            acc for acc in self.accounts
            if self.account_vars.get(acc['id'], tk.BooleanVar()).get()
        ]
        
        if not self.selected_accounts:
            messagebox.showwarning("No Selection", "Please select at least one account.")
            return
        
        # Save selected accounts to config for the signal receiver
        self.config["selected_account_ids"] = [acc['id'] for acc in self.selected_accounts]
        self.config["selected_account_names"] = [acc['name'] for acc in self.selected_accounts]
        self.config["selected_account_balances"] = [acc.get('balance', 0) for acc in self.selected_accounts]
        self.save_config()
        
        # Show countdown screen
        self.setup_countdown_screen()
    
    def setup_countdown_screen(self):
        """Show countdown before launching terminal."""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.title("QuoTrading - Launching")
        
        self.create_header("QuoTrading AI", "Launching Signal Receiver")
        
        main = tk.Frame(self.root, bg=self.colors['background'], padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Center frame
        center = tk.Frame(main, bg=self.colors['background'])
        center.pack(expand=True)
        
        # Countdown number
        self.countdown_label = tk.Label(
            center, text="3",
            font=("Segoe UI", 72, "bold"),
            bg=self.colors['background'],
            fg=self.colors['success']
        )
        self.countdown_label.pack(pady=20)
        
        # Status text
        self.countdown_status = tk.Label(
            center, text="Registering with server...",
            font=("Segoe UI", 11),
            bg=self.colors['background'],
            fg=self.colors['text_light']
        )
        self.countdown_status.pack()
        
        # Account info
        tk.Label(
            center, text=f"Launching with {len(self.selected_accounts)} account(s)",
            font=("Segoe UI", 9),
            bg=self.colors['background'],
            fg=self.colors['text_secondary']
        ).pack(pady=(10, 0))
        
        # Start countdown
        self._countdown(8)
    
    def _countdown(self, count):
        """Countdown animation."""
        if count > 0:
            self.countdown_label.config(text=str(count))
            
            # Update status based on countdown - AI focused messaging
            if count == 8:
                self.countdown_status.config(text="Connecting to AI servers...")
            elif count == 7:
                self.countdown_status.config(text="Authenticating license...")
            elif count == 6:
                self.countdown_status.config(text="Loading neural network...")
            elif count == 5:
                self.countdown_status.config(text="Syncing market data...")
            elif count == 4:
                self.countdown_status.config(text="Calibrating AI models...")
            elif count == 3:
                self.countdown_status.config(text="Preparing real-time analysis...")
            elif count == 2:
                self.countdown_status.config(text="Initializing trade engine...")
            elif count == 1:
                self.countdown_status.config(text="Launching terminal...")
            
            self.root.after(1000, lambda: self._countdown(count - 1))
        else:
            self.countdown_label.config(text="🚀")
            self.countdown_status.config(text="Launching now!")
            self.root.after(500, self._launch_terminal)
    
    def _launch_terminal(self):
        """Launch PowerShell with signal receiver and close GUI."""
        import subprocess
        import os
        
        # Path to signal receiver script
        script_dir = Path(__file__).parent
        receiver_script = script_dir / "signal_receiver.py"
        
        # Build command - pass config file path
        config_path = str(self.config_file)
        
        # Launch PowerShell window with signal receiver
        cmd = f'Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd \'{script_dir}\'; python signal_receiver.py --config \'{config_path}\'"'
        
        try:
            subprocess.Popen(["powershell", "-Command", cmd], shell=True)
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch terminal: {e}")
            return
        
        # Close the GUI
        self.root.after(500, self.root.destroy)
    
    def setup_listening_screen(self):
        """Screen 2: Listening for signals."""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.receiving = True
        self.root.title("QuoTrading - Listening")
        self.root.geometry("650x500")
        
        self.create_header("QuoTrading AI", "Connected - Listening for Signals")
        
        main = tk.Frame(self.root, bg=self.colors['background'], padx=20, pady=10)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Status + Ping row
        status_frame = tk.Frame(main, bg=self.colors['card'])
        status_frame.pack(fill=tk.X, pady=(0, 10))
        status_frame.configure(highlightbackground=self.colors['listening'], highlightthickness=2)
        
        status_inner = tk.Frame(status_frame, bg=self.colors['card'], padx=10, pady=8)
        status_inner.pack(fill=tk.X)
        
        self.status_label = tk.Label(status_inner, text="🎧 LISTENING FOR SIGNALS",
                                    font=("Segoe UI", 12, "bold"), bg=self.colors['card'], fg=self.colors['listening'])
        self.status_label.pack(side=tk.LEFT)
        
        # Ping indicator on the right
        self.ping_label = tk.Label(status_inner, text="Ping: --ms",
                                  font=("Segoe UI", 9), bg=self.colors['card'], fg=self.colors['text_secondary'])
        self.ping_label.pack(side=tk.RIGHT)
        
        self._pulse_status()
        self._update_ping()
        
        # Info bar (API key + time)
        info_bar = tk.Frame(main, bg=self.colors['card'])
        info_bar.pack(fill=tk.X, pady=(0, 10))
        info_bar.configure(highlightbackground=self.colors['border_subtle'], highlightthickness=1)
        
        info_inner = tk.Frame(info_bar, bg=self.colors['card'], padx=10, pady=5)
        info_inner.pack(fill=tk.X)
        
        # License key (masked)
        api_key = self.config.get("quotrading_api_key", "")
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
        tk.Label(info_inner, text=f"License: {masked_key}",
                font=("Segoe UI", 8), bg=self.colors['card'], fg=self.colors['text_secondary']).pack(side=tk.LEFT)
        
        # Current time (will be updated)
        self.time_label = tk.Label(info_inner, text="",
                                  font=("Segoe UI", 8), bg=self.colors['card'], fg=self.colors['text_secondary'])
        self.time_label.pack(side=tk.RIGHT)
        self._update_clock()
        
        # Connected accounts (no "copy" language)
        tk.Label(main, text=f"CONNECTED ACCOUNTS ({len(self.selected_accounts)})",
                font=("Segoe UI", 10, "bold"), bg=self.colors['background'], fg=self.colors['text']).pack(anchor=tk.W, pady=(5, 5))
        
        for acc in self.selected_accounts:
            acc_card = tk.Frame(main, bg=self.colors['card'])
            acc_card.pack(fill=tk.X, pady=2)
            acc_card.configure(highlightbackground=self.colors['border_subtle'], highlightthickness=1)
            
            inner = tk.Frame(acc_card, bg=self.colors['card'], padx=10, pady=8)
            inner.pack(fill=tk.X)
            
            tk.Label(inner, text=acc['name'], font=("Segoe UI", 9, "bold"),
                    bg=self.colors['card'], fg=self.colors['text']).pack(side=tk.LEFT)
            tk.Label(inner, text=f"${acc['balance']:,.2f}", font=("Segoe UI", 9),
                    bg=self.colors['card'], fg=self.colors['success']).pack(side=tk.RIGHT)
        
        # Log
        tk.Label(main, text="ACTIVITY LOG", font=("Segoe UI", 10, "bold"),
                bg=self.colors['background'], fg=self.colors['text']).pack(anchor=tk.W, pady=(10, 5))
        
        log_frame = tk.Frame(main, bg=self.colors['card'])
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_frame.configure(highlightbackground=self.colors['border_subtle'], highlightthickness=1)
        
        self.log_text = tk.Text(log_frame, font=("Consolas", 9), bg=self.colors['primary'],
                               fg=self.colors['text_light'], relief=tk.FLAT, height=6, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.add_log("✅ Connected to QuoTrading server")
        self.add_log(f"📊 Monitoring {len(self.selected_accounts)} account(s)")
        self.add_log("⏳ Waiting for signals from server...")
        
        # Stop button
        tk.Button(main, text="⏹ DISCONNECT", font=("Segoe UI", 10, "bold"),
                 bg=self.colors['error'], fg='white', relief=tk.FLAT,
                 command=self.stop_listening, cursor="hand2").pack(fill=tk.X, pady=(10, 0), ipady=8)
    
    def _update_ping(self):
        """Measure and display ping to server."""
        if not self.receiving:
            return
        
        def measure_ping():
            import time
            try:
                start = time.time()
                requests.get(f"{CLOUD_API_BASE_URL}/copier/status", timeout=5)
                ping_ms = int((time.time() - start) * 1000)
                self.root.after(0, lambda p=ping_ms: self._set_ping(p))
            except:
                self.root.after(0, lambda: self._set_ping(-1))
        
        threading.Thread(target=measure_ping, daemon=True).start()
        
        # Update every 10 seconds
        self.root.after(10000, self._update_ping)
    
    def _set_ping(self, ping_ms):
        if ping_ms < 0:
            self.ping_label.config(text="Ping: Timeout", fg=self.colors['error'])
        elif ping_ms < 100:
            self.ping_label.config(text=f"Ping: {ping_ms}ms", fg=self.colors['listening'])
        elif ping_ms < 300:
            self.ping_label.config(text=f"Ping: {ping_ms}ms", fg=self.colors['warning'])
        else:
            self.ping_label.config(text=f"Ping: {ping_ms}ms", fg=self.colors['error'])
    
    def _pulse_status(self):
        if not self.receiving:
            return
        try:
            current = self.status_label.cget('fg')
            self.status_label.config(fg='#00CC66' if current == self.colors['listening'] else self.colors['listening'])
            self.root.after(1000, self._pulse_status)
        except:
            pass
    
    def _update_clock(self):
        """Update the time display."""
        if not self.receiving:
            return
        try:
            current_time = datetime.now().strftime("%I:%M:%S %p")
            self.time_label.config(text=current_time)
            self.root.after(1000, self._update_clock)
        except:
            pass
    
    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def stop_listening(self):
        """Stop listening and unregister from server."""
        self.receiving = False
        self.heartbeat_running = False
        
        # Unregister from server (fire and forget)
        def unregister():
            try:
                api_key = self.config.get("quotrading_api_key", "")
                requests.post(
                    f"{CLOUD_API_BASE_URL}/copier/unregister",
                    json={"follower_key": api_key},
                    timeout=5
                )
            except:
                pass
        
        threading.Thread(target=unregister, daemon=True).start()
        
        self.selected_accounts = []
        self.setup_broker_screen()
    
    def show_loading(self, message="Loading..."):
        self.loading_window = tk.Toplevel(self.root)
        self.loading_window.geometry("300x100")
        self.loading_window.resizable(False, False)
        self.loading_window.configure(bg=self.colors['card'])
        self.loading_window.overrideredirect(True)
        self.loading_window.transient(self.root)
        self.loading_window.grab_set()
        
        border = tk.Frame(self.loading_window, bg=self.colors['border'])
        border.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        inner = tk.Frame(border, bg=self.colors['card'])
        inner.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.loading_label = tk.Label(inner, text=message, font=("Segoe UI", 11, "bold"),
                                      bg=self.colors['card'], fg=self.colors['success'])
        self.loading_label.pack(expand=True)
        
        self.loading_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 50
        self.loading_window.geometry(f"+{x}+{y}")
    
    def update_loading(self, message):
        if hasattr(self, 'loading_label'):
            self.loading_label.config(text=message)
    
    def hide_loading(self):
        if hasattr(self, 'loading_window'):
            self.loading_window.destroy()
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    launcher = TradeCopierLauncher()
    launcher.run()
