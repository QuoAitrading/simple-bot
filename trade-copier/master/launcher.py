"""
Master Launcher - YOUR dashboard to monitor trade broadcasts
Shows connected followers (ONLINE ONLY) with email and API key
Styled like Google Sheets / Admin Dashboard
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
import time
import requests
from datetime import datetime

# Config
CLOUD_API_BASE_URL = "https://quotrading-flask-api.azurewebsites.net"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


class MasterLauncher:
    """Master dashboard GUI - Spreadsheet style"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📊 QuoTrading AI - Master Dashboard")
        self.root.geometry("1100x700")
        self.root.resizable(True, True)
        self.root.minsize(900, 600)
        
        # Google Sheets-inspired colors (light theme for readability)
        self.colors = {
            'background': '#f8f9fa',
            'header_bg': '#1a73e8',
            'card': '#ffffff',
            'accent': '#1a73e8',
            'success': '#34a853',
            'warning': '#ea8600',
            'error': '#ea4335',
            'text': '#202124',
            'text_light': '#5f6368',
            'grid_header': '#f8f9fa',
            'grid_row': '#ffffff',
            'grid_row_alt': '#f8f9fa',
            'grid_border': '#dadce0',
            'online_bg': '#e6f4ea',
            'online_text': '#1e8e3e'
        }
        
        self.root.configure(bg=self.colors['background'])
        
        # State
        self.running = False
        self.followers = []
        self.trade_log = []
        self.copy_enabled = True  # Global toggle for signal broadcasting
        
        # Broker/Position tracking for auto-broadcast
        self.broker = None
        self.broker_connected = False
        self.last_position = None  # Track position to detect changes
        self.position_monitor_running = False
        
        # Load config
        self.config = self.load_config()
        
        # Check if we need setup
        if not self.config.get('broker', {}).get('username') or self.config.get('broker', {}).get('username') == 'YOUR_EMAIL@gmail.com':
            self.setup_settings_screen()
        else:
            self.setup_dashboard()
    
    def load_config(self):
        """Load master config"""
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        return {
            "api_url": CLOUD_API_BASE_URL,
            "master_key": "",
            "broker": {
                "username": "",
                "api_token": ""
            }
        }
    
    def save_config(self):
        """Save config to file"""
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def setup_settings_screen(self):
        """Settings screen with spreadsheet-style account config"""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.geometry("700x620")
        
        # Header - Blue bar like the dashboard
        header = tk.Frame(self.root, bg=self.colors['header_bg'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="⚙️ Master Account Setup", 
                font=("Segoe UI", 14, "bold"), 
                bg=self.colors['header_bg'], fg='white').pack(side=tk.LEFT, padx=20, pady=12)
        
        # Main content with light background
        main = tk.Frame(self.root, bg='white', padx=30, pady=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(main, text="Configure your master trading account",
                font=("Segoe UI", 11),
                bg='white', fg=self.colors['text_light']).pack(pady=(0, 15))
        
        # ═══════════════════════════════════════════════════════════════════
        # BROKER SELECTION SECTION
        # ═══════════════════════════════════════════════════════════════════
        broker_frame = tk.Frame(main, bg='white')
        broker_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Account Type (Prop Firm vs Live Broker)
        type_frame = tk.Frame(broker_frame, bg='white')
        type_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(type_frame, text="Account Type:", 
                font=("Segoe UI", 10, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        self.account_type_var = tk.StringVar(value=self.config.get('account_type', 'Prop Firm'))
        account_types = ['Prop Firm', 'Live Broker']
        
        type_dropdown = ttk.Combobox(type_frame, textvariable=self.account_type_var,
                                     values=account_types, state='readonly', width=20)
        type_dropdown.pack(side=tk.LEFT, padx=10)
        type_dropdown.bind('<<ComboboxSelected>>', self.update_broker_options)
        
        # Broker Selection
        broker_select_frame = tk.Frame(broker_frame, bg='white')
        broker_select_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(broker_select_frame, text="Broker:", 
                font=("Segoe UI", 10, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        self.broker_var = tk.StringVar(value=self.config.get('broker_name', 'TopStep'))
        self.broker_dropdown = ttk.Combobox(broker_select_frame, textvariable=self.broker_var,
                                            state='readonly', width=20)
        self.broker_dropdown.pack(side=tk.LEFT, padx=10)
        self.update_broker_options()
        
        # ═══════════════════════════════════════════════════════════════════
        # CREDENTIALS TABLE
        # ═══════════════════════════════════════════════════════════════════
        tk.Frame(main, bg=self.colors['grid_border'], height=1).pack(fill=tk.X, pady=10)
        
        # Spreadsheet-style table
        table_frame = tk.Frame(main, bg=self.colors['grid_border'], padx=1, pady=1)
        table_frame.pack(fill=tk.X)
        
        # Headers row
        headers = tk.Frame(table_frame, bg=self.colors['grid_header'])
        headers.pack(fill=tk.X)
        
        tk.Label(headers, text="Setting", width=20, anchor='w',
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['grid_header'], fg=self.colors['text'],
                padx=10, pady=8).pack(side=tk.LEFT)
        
        tk.Label(headers, text="Value", width=50, anchor='w',
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['grid_header'], fg=self.colors['text'],
                padx=10, pady=8).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Entry variables
        self.master_key_var = tk.StringVar(value=self.config.get('master_key', ''))
        self.username_var = tk.StringVar(value=self.config.get('broker', {}).get('username', ''))
        self.api_token_var = tk.StringVar(value=self.config.get('broker', {}).get('api_token', ''))
        
        # Rows
        self.create_table_row(table_frame, "Master Key (License)", self.master_key_var)
        self.create_table_row(table_frame, "Broker Username/Email", self.username_var)
        self.create_table_row(table_frame, "API Token", self.api_token_var, show='*')
        
        # Help text
        help_frame = tk.Frame(main, bg='white')
        help_frame.pack(fill=tk.X, pady=15)
        
        tk.Label(help_frame, text="ℹ️ Your API token can be found in ProjectX / Broker settings",
                font=("Segoe UI", 9),
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        
        tk.Label(help_frame, text="   This is the MASTER account - your trades will be auto-broadcast to followers",
                font=("Segoe UI", 9),
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        
        # Buttons
        btn_frame = tk.Frame(main, bg='white')
        btn_frame.pack(fill=tk.X, pady=30)
        
        save_btn = tk.Button(btn_frame, text="💾 Save & Start Dashboard",
                            font=("Segoe UI", 11, "bold"),
                            bg=self.colors['success'], fg='white',
                            activebackground='#2d9249',
                            relief=tk.FLAT, padx=30, pady=12,
                            cursor='hand2',
                            command=self.save_and_start)
        save_btn.pack(side=tk.RIGHT)
        
        # If config exists, add switch to dashboard button
        if self.config.get('broker', {}).get('username'):
            tk.Button(btn_frame, text="← Back to Dashboard",
                     font=("Segoe UI", 10),
                     bg=self.colors['grid_header'], fg=self.colors['text'],
                     activebackground='#e8eaed',
                     relief=tk.FLAT, padx=15, pady=8,
                     cursor='hand2',
                     command=self.setup_dashboard).pack(side=tk.LEFT)
    
    def update_broker_options(self, event=None):
        """Update broker dropdown based on account type selection"""
        account_type = self.account_type_var.get()
        
        if account_type == 'Prop Firm':
            # Add more prop firms here as needed
            brokers = ['TopStep', 'Apex', 'The5ers', 'FTMO']
        else:
            # Live brokers
            brokers = ['Tradovate', 'NinjaTrader', 'Interactive Brokers']
        
        self.broker_dropdown['values'] = brokers
        
        # Set default if current value not in list
        if self.broker_var.get() not in brokers:
            self.broker_var.set(brokers[0])
    
    def create_table_row(self, parent, label, var, show=None):
        """Create a spreadsheet-style table row"""
        row = tk.Frame(parent, bg=self.colors['grid_row'])
        row.pack(fill=tk.X)
        
        # Separator
        sep = tk.Frame(parent, bg=self.colors['grid_border'], height=1)
        sep.pack(fill=tk.X)
        
        # Label cell
        tk.Label(row, text=label, width=20, anchor='w',
                font=("Segoe UI", 10),
                bg=self.colors['grid_row'], fg=self.colors['text'],
                padx=10, pady=10).pack(side=tk.LEFT)
        
        # Vertical separator
        tk.Frame(row, bg=self.colors['grid_border'], width=1).pack(side=tk.LEFT, fill=tk.Y)
        
        # Entry cell with border
        entry_frame = tk.Frame(row, bg=self.colors['grid_row'])
        entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=8)
        
        entry = tk.Entry(entry_frame, textvariable=var,
                        font=("Segoe UI", 10),
                        bg='white', fg=self.colors['text'],
                        insertbackground=self.colors['text'],
                        relief=tk.SOLID, borderwidth=1, show=show)
        entry.pack(fill=tk.X, ipady=4)
    
    def save_and_start(self):
        """Save settings and start dashboard"""
        # Validate
        if not self.master_key_var.get().strip():
            messagebox.showerror("Error", "Please enter your Master Key (License)")
            return
        if not self.username_var.get().strip():
            messagebox.showerror("Error", "Please enter your Broker Username/Email")
            return
        if not self.api_token_var.get().strip():
            messagebox.showerror("Error", "Please enter your API Token")
            return
        
        # Save config
        self.config['master_key'] = self.master_key_var.get().strip()
        self.config['account_type'] = self.account_type_var.get()
        self.config['broker_name'] = self.broker_var.get()
        self.config['broker'] = {
            'username': self.username_var.get().strip(),
            'api_token': self.api_token_var.get().strip()
        }
        self.config['api_url'] = CLOUD_API_BASE_URL
        self.save_config()
        
        # Switch to dashboard
        self.setup_dashboard()
    
    def setup_dashboard(self):
        """Create the main dashboard UI - Spreadsheet Style"""
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.geometry("1100x700")
        
        # ═══════════════════════════════════════════════════════════════════
        # HEADER - Blue bar like Google Sheets
        # ═══════════════════════════════════════════════════════════════════
        header = tk.Frame(self.root, bg=self.colors['header_bg'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Left side - Title
        header_left = tk.Frame(header, bg=self.colors['header_bg'])
        header_left.pack(side=tk.LEFT, padx=20, pady=10)
        
        tk.Label(header_left, text="📊 QuoTrading", 
                font=("Segoe UI", 14, "bold"), 
                bg=self.colors['header_bg'], fg='white').pack(side=tk.LEFT)
        
        tk.Label(header_left, text="  Master Dashboard", 
                font=("Segoe UI", 14), 
                bg=self.colors['header_bg'], fg='white').pack(side=tk.LEFT)
        
        # Right side - Buttons
        header_right = tk.Frame(header, bg=self.colors['header_bg'])
        header_right.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Copy Toggle Button - Prominent position
        self.copy_toggle_btn = tk.Button(header_right, text="📡 SIGNALS: ON",
                               font=("Segoe UI", 10, "bold"),
                               bg='#00cc6a', fg='white',
                               activebackground='#00aa55',
                               relief=tk.FLAT, padx=20, pady=5,
                               cursor='hand2',
                               command=self.toggle_copy_enabled)
        self.copy_toggle_btn.pack(side=tk.LEFT, padx=10)
        
        self.last_update_label = tk.Label(header_right, text="Last update: --",
            font=("Segoe UI", 9),
            bg=self.colors['header_bg'], fg='#b3d4fc')
        self.last_update_label.pack(side=tk.LEFT, padx=10)
        
        refresh_btn = tk.Button(header_right, text="🔄 Refresh",
                               font=("Segoe UI", 10),
                               bg='#1765cc', fg='white',
                               activebackground='#1557b0',
                               relief=tk.FLAT, padx=15, pady=3,
                               cursor='hand2',
                               command=self.manual_refresh)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        settings_btn = tk.Button(header_right, text="⚙️ Settings",
                                font=("Segoe UI", 10),
                                bg='#1765cc', fg='white',
                                activebackground='#1557b0',
                                relief=tk.FLAT, padx=15, pady=3,
                                cursor='hand2',
                                command=self.setup_settings_screen)
        settings_btn.pack(side=tk.LEFT, padx=5)
        
        # ═══════════════════════════════════════════════════════════════════
        # STATS BAR - Quick metrics
        # ═══════════════════════════════════════════════════════════════════
        stats_bar = tk.Frame(self.root, bg='white', height=70)
        stats_bar.pack(fill=tk.X)
        stats_bar.pack_propagate(False)
        
        # Stats container
        stats_inner = tk.Frame(stats_bar, bg='white')
        stats_inner.pack(side=tk.LEFT, padx=20, pady=12)
        
        # Online Now stat
        stat1 = tk.Frame(stats_inner, bg='white')
        stat1.pack(side=tk.LEFT, padx=(0, 40))
        tk.Label(stat1, text="ONLINE NOW", font=("Segoe UI", 9), 
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        self.online_count_label = tk.Label(stat1, text="0", 
                font=("Segoe UI", 24, "bold"), 
                bg='white', fg=self.colors['success'])
        self.online_count_label.pack(anchor='w')
        
        # Total Connected stat
        stat2 = tk.Frame(stats_inner, bg='white')
        stat2.pack(side=tk.LEFT, padx=(0, 40))
        tk.Label(stat2, text="TOTAL REGISTERED", font=("Segoe UI", 9), 
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        self.total_count_label = tk.Label(stat2, text="0", 
                font=("Segoe UI", 24, "bold"), 
                bg='white', fg=self.colors['text'])
        self.total_count_label.pack(anchor='w')
        
        # Server Status stat
        stat3 = tk.Frame(stats_inner, bg='white')
        stat3.pack(side=tk.LEFT, padx=(0, 40))
        tk.Label(stat3, text="SERVER STATUS", font=("Segoe UI", 9), 
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        self.server_status_label = tk.Label(stat3, text="● Connected", 
                font=("Segoe UI", 14, "bold"), 
                bg='white', fg=self.colors['success'])
        self.server_status_label.pack(anchor='w')
        
        # Separator line
        tk.Frame(self.root, bg=self.colors['grid_border'], height=1).pack(fill=tk.X)
        
        # ═══════════════════════════════════════════════════════════════════
        # MAIN CONTENT - Spreadsheet table
        # ═══════════════════════════════════════════════════════════════════
        content = tk.Frame(self.root, bg='white')
        content.pack(fill=tk.BOTH, expand=True)
        
        # Section header
        section_header = tk.Frame(content, bg='white')
        section_header.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(section_header, text="👥 Online Users", 
                font=("Segoe UI", 14, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        tk.Label(section_header, text="(Only showing users currently connected)", 
                font=("Segoe UI", 10),
                bg='white', fg=self.colors['text_light']).pack(side=tk.LEFT, padx=10)
        
        # ═══════════════════════════════════════════════════════════════════
        # SPREADSHEET TABLE - Using Treeview
        # ═══════════════════════════════════════════════════════════════════
        table_frame = tk.Frame(content, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Configure Treeview style for spreadsheet look
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Spreadsheet.Treeview",
            background="white",
            foreground=self.colors['text'],
            fieldbackground="white",
            font=("Segoe UI", 10),
            rowheight=40)  # Taller rows for more info
        
        style.configure("Spreadsheet.Treeview.Heading",
            background=self.colors['grid_header'],
            foreground=self.colors['text'],
            font=("Segoe UI", 10, "bold"),
            relief="flat")
        
        style.map("Spreadsheet.Treeview",
            background=[('selected', '#e8f0fe')],
            foreground=[('selected', self.colors['text'])])
        
        style.map("Spreadsheet.Treeview.Heading",
            background=[('active', '#eeeeee')])
        
        # Create Treeview with comprehensive columns
        columns = ('name', 'license', 'copy_status', 'signals', 'position', 'last_active')
        self.users_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                       style="Spreadsheet.Treeview")
        
        # Define columns - comprehensive monitoring
        self.users_tree.heading('name', text='Account Name')
        self.users_tree.heading('license', text='License Key')
        self.users_tree.heading('copy_status', text='Copy')
        self.users_tree.heading('signals', text='Signals (Exec/Recv)')
        self.users_tree.heading('position', text='Current Position')
        self.users_tree.heading('last_active', text='Last Active')
        
        # Column widths - optimized for monitoring
        self.users_tree.column('name', width=180, minwidth=120)
        self.users_tree.column('license', width=150, minwidth=100)
        self.users_tree.column('copy_status', width=80, minwidth=60)
        self.users_tree.column('signals', width=130, minwidth=100)
        self.users_tree.column('position', width=180, minwidth=120)
        self.users_tree.column('last_active', width=100, minwidth=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack table
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure row tags for styling
        self.users_tree.tag_configure('online', background=self.colors['online_bg'])
        self.users_tree.tag_configure('long_position', background='#e8f0fe')
        self.users_tree.tag_configure('short_position', background='#fce8e6')
        self.users_tree.tag_configure('copy_off', background='#fff3e0')  # Orange tint for copy disabled
        
        # ═══════════════════════════════════════════════════════════════════
        # FOOTER - Status bar
        # ═══════════════════════════════════════════════════════════════════
        footer = tk.Frame(self.root, bg=self.colors['grid_header'], height=35)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        
        self.status_label = tk.Label(footer, 
            text=f"● Master Key: {self.config.get('master_key', 'Not set')[:12]}...",
            font=("Segoe UI", 9),
            bg=self.colors['grid_header'], fg=self.colors['text_light'])
        self.status_label.pack(side=tk.LEFT, padx=20, pady=8)
        
        self.connection_label = tk.Label(footer, 
            text="📡 Signals ON | Monitoring every 500ms",
            font=("Segoe UI", 9),
            bg=self.colors['grid_header'], fg=self.colors['text_light'])
        self.connection_label.pack(side=tk.RIGHT, padx=20, pady=8)
        
        # Start polling for followers
        self.start_polling()
        
        # Connect to YOUR broker and start monitoring for auto-broadcast
        self.connect_broker_and_monitor()
    
    def manual_refresh(self):
        """Manual refresh button handler"""
        self.refresh_followers()
        self.last_update_label.config(text=f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    def toggle_copy_enabled(self):
        """Toggle the global copy enabled/disabled state"""
        self.copy_enabled = not self.copy_enabled
        
        if self.copy_enabled:
            self.copy_toggle_btn.config(
                text="📡 SIGNALS: ON",
                bg='#00cc6a',
                activebackground='#00aa55'
            )
            status_msg = "✅ Signal broadcasting ENABLED - Your trades will be copied"
        else:
            self.copy_toggle_btn.config(
                text="📡 SIGNALS: OFF",
                bg='#cc0000',
                activebackground='#aa0000'
            )
            status_msg = "⛔ Signal broadcasting DISABLED - Trading solo (no copying)"
        
        # Update status label
        self.update_copy_status_label()
        print(f"\n{'='*60}")
        print(status_msg)
        print(f"{'='*60}\n")
    
    def update_copy_status_label(self):
        """Update the footer status label with copy state"""
        try:
            if hasattr(self, 'connection_label'):
                if self.copy_enabled:
                    self.connection_label.config(text="📡 Signals ON | Monitoring every 500ms")
                else:
                    self.connection_label.config(text="⛔ Signals OFF | Solo trading mode")
        except:
            pass
    
    def start_polling(self):
        """Start background thread to poll for followers - FAST for real-time monitoring"""
        def poll():
            while True:
                try:
                    self.refresh_followers()
                except:
                    pass
                time.sleep(2)  # Poll every 2 seconds for near real-time updates
        
        thread = threading.Thread(target=poll, daemon=True)
        thread.start()
    
    def refresh_followers(self):
        """Refresh the followers list from API"""
        try:
            resp = requests.get(f"{CLOUD_API_BASE_URL}/copier/followers", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                followers = data.get('followers', [])
                
                # Update UI on main thread
                self.root.after(0, lambda: self.update_followers_ui(followers))
        except:
            pass
    
    def is_online(self, last_heartbeat: str) -> bool:
        """Check if follower is online based on heartbeat (within 60 seconds)"""
        if not last_heartbeat:
            return False
        try:
            # Parse ISO datetime
            if isinstance(last_heartbeat, str):
                hb_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
            else:
                hb_time = last_heartbeat
            
            # Make naive for comparison
            if hb_time.tzinfo:
                hb_time = hb_time.replace(tzinfo=None)
            
            seconds_since = (datetime.now() - hb_time).total_seconds()
            return seconds_since < 60  # Online if heartbeat within 60 seconds
        except:
            return False
    
    def update_followers_ui(self, followers):
        """Update the followers display - ONLINE ONLY in spreadsheet format"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Calculate online status from last_heartbeat and filter
            online_followers = []
            for f in followers:
                if self.is_online(f.get('last_heartbeat', '')):
                    online_followers.append(f)
            
            total_count = len(followers)
            online_count = len(online_followers)
            
            # Update stats labels
            try:
                self.online_count_label.config(text=str(online_count))
                self.total_count_label.config(text=str(total_count))
                self.last_update_label.config(text=f"Last update: {datetime.now().strftime('%H:%M:%S')}")
            except:
                pass
            
            # Clear existing tree items
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            
            if not online_followers:
                # Show empty state message in the first row
                self.users_tree.insert('', 'end', values=(
                    'No users currently online', '', '', '', '', ''
                ))
                return
            
            # Add each online follower with comprehensive monitoring data
            for f in online_followers:
                # Account name
                name = f.get('name', 'Unknown User')
                
                # License key (client_id) - show partial for identification
                license_key = f.get('client_id', '')
                if license_key:
                    license_display = license_key[:16] if len(license_key) > 16 else license_key
                else:
                    license_display = '—'
                
                # Copy status
                copy_enabled = f.get('copy_enabled', True)
                copy_status = '✅ ON' if copy_enabled else '❌ OFF'
                
                # Signals executed / received - KEY MONITORING DATA
                signals_received = f.get('signals_received', 0)
                signals_executed = f.get('signals_executed', 0)
                signals_text = f"{signals_executed} / {signals_received}"
                
                # Position info - detailed with symbol
                pos = f.get('current_position')
                if pos and pos.get('quantity', 0) != 0:
                    qty = pos.get('quantity', 0)
                    sym = pos.get('symbol', 'N/A')
                    if qty > 0:
                        position_text = f"🟢 LONG {qty} {sym}"
                        tag = 'long_position'
                    else:
                        position_text = f"🔴 SHORT {abs(qty)} {sym}"
                        tag = 'short_position'
                else:
                    position_text = "— Flat"
                    tag = 'online' if copy_enabled else 'copy_off'
                
                # If copy is disabled, override tag
                if not copy_enabled:
                    tag = 'copy_off'
                
                # Last active from heartbeat
                last_heartbeat = f.get('last_heartbeat', '')
                last_active_text = self.time_ago(last_heartbeat) if last_heartbeat else 'Just now'
                
                # Insert row with all monitoring data
                self.users_tree.insert('', 'end', values=(
                    name,
                    license_display,
                    copy_status,
                    signals_text,
                    position_text,
                    last_active_text
                ), tags=(tag,))
            
        except tk.TclError:
            return
        except Exception as e:
            print(f"Error updating followers UI: {e}")
            return
    
    def time_ago(self, date_str):
        """Convert datetime string to 'X ago' format"""
        if not date_str:
            return 'Never'
        try:
            # Parse the date string
            if isinstance(date_str, str):
                # Try ISO format
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                date = date_str
            
            # Calculate difference
            now = datetime.now()
            if date.tzinfo:
                # Make naive for comparison
                date = date.replace(tzinfo=None)
            
            seconds = (now - date).total_seconds()
            
            if seconds < 0:
                return 'Just now'
            if seconds < 60:
                return f'{int(seconds)}s ago'
            if seconds < 3600:
                return f'{int(seconds // 60)}m ago'
            if seconds < 86400:
                return f'{int(seconds // 3600)}h ago'
            return f'{int(seconds // 86400)}d ago'
        except:
            return 'Unknown'
    
    def connect_broker_and_monitor(self):
        """Connect to YOUR broker and start monitoring positions for auto-broadcast"""
        print("=" * 60)
        print("🔧 MASTER BROKER CONNECTION STARTING...")
        print("=" * 60)
        import asyncio
        
        def run_broker_connection():
            try:
                # Add parent path for imports
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from shared.copier_broker import CopierBroker
                
                # Create broker with your credentials
                username = self.config.get('broker', {}).get('username', '')
                api_token = self.config.get('broker', {}).get('api_token', '')
                
                if not username or not api_token:
                    self.root.after(0, lambda: self.update_broker_status("❌ No credentials"))
                    return
                
                self.root.after(0, lambda: self.update_broker_status("⏳ Connecting..."))
                
                # Connect async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                self.broker = CopierBroker(username=username, api_token=api_token)
                print("🔌 Attempting to connect to your broker...")
                connected = loop.run_until_complete(self.broker.connect())
                print(f"🔌 Broker connection result: {connected}")
                
                if connected:
                    self.broker_connected = True
                    self.root.after(0, lambda: self.update_broker_status("✅ Connected - Monitoring"))
                    print("📡 Position monitoring started - checking every 500ms")
                    
                    # Start position monitoring loop
                    self.position_monitor_running = True
                    poll_count = 0
                    while self.position_monitor_running:
                        try:
                            positions = loop.run_until_complete(self.broker.get_positions())
                            poll_count += 1
                            # Only log every 60 polls (30 seconds) unless position exists
                            if positions or poll_count % 60 == 0:
                                if poll_count % 60 == 0:
                                    print(f"📊 Still monitoring... (Poll #{poll_count}, {len(positions)} position(s))")
                                elif positions:
                                    for p in positions:
                                        print(f"   🎯 {p['symbol']}: {p['quantity']} contracts")
                            self.check_position_change(positions, loop)
                        except Exception as e:
                            if poll_count % 60 == 0:
                                print(f"❌ Position poll error: {e}")
                        time.sleep(0.5)  # Check every 500ms for fast detection
                else:
                    self.root.after(0, lambda: self.update_broker_status("❌ Connection failed"))
                
                loop.close()
                
            except Exception as e:
                self.root.after(0, lambda: self.update_broker_status(f"❌ Error: {str(e)[:20]}"))
        
        thread = threading.Thread(target=run_broker_connection, daemon=True)
        thread.start()
    
    def update_broker_status(self, status):
        """Update the broker status label in the dashboard"""
        try:
            if hasattr(self, 'server_status_label'):
                self.server_status_label.config(text=status)
        except:
            pass
    
    def check_position_change(self, positions, loop):
        """Check if position changed and broadcast if it did"""
        import asyncio
        
        # Get current position summary
        current_pos = None
        for pos in positions:
            qty = pos.get('quantity', 0)
            if qty != 0:
                current_pos = {
                    'symbol': pos.get('symbol', ''),
                    'quantity': qty,
                    'side': 'LONG' if qty > 0 else 'SHORT'
                }
                break
        
        # Compare with last known position
        if current_pos != self.last_position:
            old_pos = self.last_position
            self.last_position = current_pos
            
            # Determine what changed and broadcast
            if old_pos is None and current_pos is not None:
                # NEW POSITION OPENED
                signal = {
                    'action': 'OPEN',
                    'symbol': current_pos['symbol'],
                    'side': 'BUY' if current_pos['quantity'] > 0 else 'SELL',
                    'quantity': abs(current_pos['quantity']),
                    'entry_price': 0,  # We don't have this from positions
                    'timestamp': datetime.now().isoformat()
                }
                self.broadcast_signal(signal)
                self.root.after(0, lambda: self.add_trade_log(f"📤 BROADCAST: OPEN {current_pos['side']} {abs(current_pos['quantity'])} {current_pos['symbol']}"))
                
            elif old_pos is not None and current_pos is None:
                # POSITION CLOSED (FLATTEN)
                signal = {
                    'action': 'FLATTEN',
                    'symbol': old_pos['symbol'],
                    'side': 'SELL' if old_pos['quantity'] > 0 else 'BUY',
                    'quantity': abs(old_pos['quantity']),
                    'exit_price': 0,
                    'timestamp': datetime.now().isoformat()
                }
                self.broadcast_signal(signal)
                self.root.after(0, lambda: self.add_trade_log(f"📤 BROADCAST: FLATTEN {old_pos['symbol']}"))
                
            elif old_pos is not None and current_pos is not None:
                # POSITION CHANGED (size or direction)
                if old_pos['symbol'] == current_pos['symbol']:
                    # Same symbol, quantity changed
                    old_qty = old_pos['quantity']
                    new_qty = current_pos['quantity']
                    
                    if (old_qty > 0 and new_qty > 0) or (old_qty < 0 and new_qty < 0):
                        # Same direction, size changed
                        diff = new_qty - old_qty
                        if diff > 0:
                            action = 'OPEN'  # Added to position
                            side = 'BUY' if new_qty > 0 else 'SELL'
                        else:
                            action = 'CLOSE'  # Reduced position
                            side = 'SELL' if new_qty > 0 else 'BUY'
                            diff = abs(diff)
                        
                        signal = {
                            'action': action,
                            'symbol': current_pos['symbol'],
                            'side': side,
                            'quantity': abs(diff),
                            'timestamp': datetime.now().isoformat()
                        }
                        self.broadcast_signal(signal)
                        self.root.after(0, lambda a=action, s=side, d=abs(diff), sym=current_pos['symbol']: 
                            self.add_trade_log(f"📤 BROADCAST: {a} {s} {d} {sym}"))
    
    def broadcast_signal(self, signal):
        """Send signal to all connected followers via API - only if copy enabled"""
        # Check if copy is enabled - don't broadcast if disabled
        if not self.copy_enabled:
            msg = f"⛔ Signal NOT broadcast (copy disabled): {signal.get('action')} {signal.get('side', '')} {signal.get('quantity', '')} {signal.get('symbol', '')}"
            self.root.after(0, lambda: self.add_trade_log(msg))
            return
        
        try:
            master_key = self.config.get('master_key', '')
            resp = requests.post(
                f"{CLOUD_API_BASE_URL}/copier/broadcast",
                json={
                    "master_key": master_key,
                    "signal": signal
                },
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                count = data.get('received_count', 0) + data.get('websocket_count', 0)
                msg = f"📡 Signal sent to {count} followers"
                self.root.after(0, lambda: self.add_trade_log(msg))
        except Exception as e:
            msg = f"❌ Broadcast error: {e}"
            self.root.after(0, lambda: self.add_trade_log(msg))
    
    def add_trade_log(self, message):
        """Add message to trade log (for future UI element)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.trade_log.append(f"[{timestamp}] {message}")
        print(f"[{timestamp}] {message}")  # Also print to console
    
    def run(self):
        """Start the launcher"""
        self.root.mainloop()


def main():
    """Entry point"""
    launcher = MasterLauncher()
    launcher.run()


if __name__ == "__main__":
    main()

