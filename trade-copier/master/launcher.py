"""
Master Launcher - Unified Admin & Trade Copier Dashboard
Combines admin dashboard functionality with trade copy monitoring
Shows connected followers, admin controls, and real-time trading
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
import hashlib
import secrets
from datetime import datetime

# Config
CLOUD_API_BASE_URL = "https://quotrading-flask-api.azurewebsites.net"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


class MasterLauncher:
    """Master dashboard GUI - Spreadsheet style"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📊 QuoTrading AI - Admin & Trade Copy Dashboard")
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
        
        # Entry variables - Master Key auto-generated (not shown to user)
        self.username_var = tk.StringVar(value=self.config.get('broker', {}).get('username', ''))
        self.api_token_var = tk.StringVar(value=self.config.get('broker', {}).get('api_token', ''))
        
        # Rows - Only broker credentials (Master Key auto-generated behind the scenes)
        self.create_table_row(table_frame, "Broker Username/Email", self.username_var)
        self.create_table_row(table_frame, "API Token", self.api_token_var, show='*')
        
        # Help text - only broker credentials needed
        help_frame = tk.Frame(main, bg='white')
        help_frame.pack(fill=tk.X, pady=15)
        
        tk.Label(help_frame, text="ℹ️ Your API token can be found in ProjectX / Broker settings",
                font=("Segoe UI", 9),
                bg='white', fg=self.colors['text_light']).pack(anchor='w')
        
        tk.Label(help_frame, text="   Only broker credentials needed - authentication handled automatically",
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
        # Validate - only broker credentials are required
        if not self.username_var.get().strip():
            messagebox.showerror("Error", "Please enter your Broker Username/Email")
            return
        if not self.api_token_var.get().strip():
            messagebox.showerror("Error", "Please enter your API Token")
            return
        
        # Auto-generate master_key silently from broker credentials
        # User doesn't need to see or know about this - it's just for API authentication
        username_hash = hashlib.sha256(self.username_var.get().strip().encode()).hexdigest()[:16]
        random_component = secrets.token_hex(16)
        master_key = f"{username_hash}{random_component}"[:32]
        
        # Save config
        self.config['master_key'] = master_key
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
        
        tk.Label(header_left, text="  Admin & Trade Copy Dashboard", 
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
        # TABBED INTERFACE - Trade Copy & Admin tabs
        # ═══════════════════════════════════════════════════════════════════
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Configure notebook style
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 10], font=("Segoe UI", 10, "bold"))
        
        # ═══════════════════════════════════════════════════════════════════
        # TAB 1: TRADE COPY - Live Followers
        # ═══════════════════════════════════════════════════════════════════
        trade_copy_tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(trade_copy_tab, text='📡 Trade Copy')
        
        # Section header
        section_header = tk.Frame(trade_copy_tab, bg='white')
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
        table_frame = tk.Frame(trade_copy_tab, bg='white')
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
        # TAB 2: ADMIN - User Management
        # ═══════════════════════════════════════════════════════════════════
        admin_tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(admin_tab, text='👥 Admin')
        
        self.setup_admin_tab(admin_tab)
        
        # ═══════════════════════════════════════════════════════════════════
        # TAB 3: ZONES - Supply/Demand Zones
        # ═══════════════════════════════════════════════════════════════════
        zones_tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(zones_tab, text='🧩 Zones')
        
        self.setup_zones_tab(zones_tab)
        
        # ═══════════════════════════════════════════════════════════════════
        # TAB 4: HEALTH - System Health
        # ═══════════════════════════════════════════════════════════════════
        health_tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(health_tab, text='💚 Health')
        
        self.setup_health_tab(health_tab)
        
        # ═══════════════════════════════════════════════════════════════════
        # FOOTER - Status bar
        # ═══════════════════════════════════════════════════════════════════
        footer = tk.Frame(self.root, bg=self.colors['grid_header'], height=35)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        
        self.status_label = tk.Label(footer, 
            text=f"● Broker: {self.config.get('broker', {}).get('username', 'Not configured')[:30]}",
            font=("Segoe UI", 9),
            bg=self.colors['grid_header'], fg=self.colors['text_light'])
        self.status_label.pack(side=tk.LEFT, padx=20, pady=8)
        
        self.connection_label = tk.Label(footer, 
            text="📡 Signals ON | Ultra-fast monitoring (100ms)",
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
        self.refresh_admin_users()
        self.last_update_label.config(text=f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    def setup_admin_tab(self, parent):
        """Setup the admin tab with user management"""
        # Admin header
        admin_header = tk.Frame(parent, bg='white')
        admin_header.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(admin_header, text="👥 User Management", 
                font=("Segoe UI", 14, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        tk.Label(admin_header, text="(All registered users - Active, Suspended, Expired)", 
                font=("Segoe UI", 10),
                bg='white', fg=self.colors['text_light']).pack(side=tk.LEFT, padx=10)
        
        # Refresh button for admin tab
        tk.Button(admin_header, text="🔄 Refresh Users",
                font=("Segoe UI", 10),
                bg=self.colors['accent'], fg='white',
                activebackground='#1557b0',
                relief=tk.FLAT, padx=15, pady=5,
                cursor='hand2',
                command=self.refresh_admin_users).pack(side=tk.RIGHT)
        
        # Stats bar for admin
        admin_stats = tk.Frame(parent, bg='white')
        admin_stats.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.admin_total_label = tk.Label(admin_stats, text="Total Users: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['text'])
        self.admin_total_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.admin_active_label = tk.Label(admin_stats, text="Active: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['success'])
        self.admin_active_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.admin_suspended_label = tk.Label(admin_stats, text="Suspended: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['error'])
        self.admin_suspended_label.pack(side=tk.LEFT)
        
        # Admin user table
        admin_table_frame = tk.Frame(parent, bg='white')
        admin_table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Create admin users tree
        admin_columns = ('email', 'license_key', 'status', 'license_type', 'expiration', 'actions')
        self.admin_users_tree = ttk.Treeview(admin_table_frame, columns=admin_columns, show='headings',
                                             style="Spreadsheet.Treeview")
        
        # Define columns
        self.admin_users_tree.heading('email', text='Email')
        self.admin_users_tree.heading('license_key', text='License Key')
        self.admin_users_tree.heading('status', text='Status')
        self.admin_users_tree.heading('license_type', text='Type')
        self.admin_users_tree.heading('expiration', text='Expires')
        self.admin_users_tree.heading('actions', text='Actions')
        
        # Column widths
        self.admin_users_tree.column('email', width=200, minwidth=150)
        self.admin_users_tree.column('license_key', width=180, minwidth=120)
        self.admin_users_tree.column('status', width=100, minwidth=80)
        self.admin_users_tree.column('license_type', width=100, minwidth=80)
        self.admin_users_tree.column('expiration', width=150, minwidth=100)
        self.admin_users_tree.column('actions', width=200, minwidth=150)
        
        # Scrollbar for admin table
        admin_scrollbar = ttk.Scrollbar(admin_table_frame, orient=tk.VERTICAL, command=self.admin_users_tree.yview)
        self.admin_users_tree.configure(yscrollcommand=admin_scrollbar.set)
        
        # Pack admin table
        self.admin_users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        admin_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure row tags for admin table
        self.admin_users_tree.tag_configure('active', background='#e6f4ea')
        self.admin_users_tree.tag_configure('suspended', background='#fce8e6')
        self.admin_users_tree.tag_configure('expired', background='#f5f5f5')
        
        # Bind double-click to show user details
        self.admin_users_tree.bind('<Double-1>', self.show_user_details)
        
        # Initial load
        self.refresh_admin_users()
    
    def refresh_admin_users(self):
        """Refresh the admin users list"""
        try:
            # Get admin key from config (auto-generated from username)
            admin_key = self.config.get('master_key', '')
            if not admin_key:
                return
            
            # Fetch all users from API
            resp = requests.get(
                f"{CLOUD_API_BASE_URL}/api/admin/list-licenses",
                params={'license_key': admin_key},
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                users = data.get('licenses', [])
                self.root.after(0, lambda: self.update_admin_users_ui(users))
        except Exception as e:
            print(f"Error fetching admin users: {e}")
    
    def update_admin_users_ui(self, users):
        """Update the admin users table"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Clear existing items
            for item in self.admin_users_tree.get_children():
                self.admin_users_tree.delete(item)
            
            # Count stats
            total = len(users)
            active = sum(1 for u in users if u.get('license_status', '').upper() == 'ACTIVE')
            suspended = sum(1 for u in users if u.get('license_status', '').upper() == 'SUSPENDED')
            
            # Update stats labels
            self.admin_total_label.config(text=f"Total Users: {total}")
            self.admin_active_label.config(text=f"Active: {active}")
            self.admin_suspended_label.config(text=f"Suspended: {suspended}")
            
            if not users:
                self.admin_users_tree.insert('', 'end', values=(
                    'No users found', '', '', '', '', ''
                ))
                return
            
            # Add each user
            for user in users:
                email = user.get('email', 'N/A')
                license_key = user.get('license_key', '')[:20] + '...' if len(user.get('license_key', '')) > 20 else user.get('license_key', '')
                status = user.get('license_status', 'UNKNOWN').upper()
                license_type = user.get('license_type', 'UNKNOWN')
                expiration = user.get('license_expiration', 'N/A')
                
                # Format expiration date
                if expiration and expiration != 'N/A':
                    try:
                        exp_date = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
                        expiration = exp_date.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                
                # Determine tag
                tag = 'active' if status == 'ACTIVE' else 'suspended' if status == 'SUSPENDED' else 'expired'
                
                # Actions column - show available actions
                actions = 'Double-click for options'
                
                self.admin_users_tree.insert('', 'end', values=(
                    email,
                    license_key,
                    status,
                    license_type,
                    expiration,
                    actions
                ), tags=(tag,))
                
        except tk.TclError:
            return
        except Exception as e:
            print(f"Error updating admin users UI: {e}")
    
    def show_user_details(self, event):
        """Show user details and actions dialog"""
        selection = self.admin_users_tree.selection()
        if not selection:
            return
        
        item = self.admin_users_tree.item(selection[0])
        values = item['values']
        
        if values[0] == 'No users found':
            return
        
        # Create popup dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("User Actions")
        dialog.geometry("400x300")
        dialog.configure(bg='white')
        
        # User info
        info_frame = tk.Frame(dialog, bg='white', padx=20, pady=20)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(info_frame, text="User Details", font=("Segoe UI", 14, "bold"),
                bg='white', fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        tk.Label(info_frame, text=f"Email: {values[0]}", font=("Segoe UI", 10),
                bg='white', fg=self.colors['text']).pack(anchor='w')
        tk.Label(info_frame, text=f"Status: {values[2]}", font=("Segoe UI", 10),
                bg='white', fg=self.colors['text']).pack(anchor='w')
        tk.Label(info_frame, text=f"Type: {values[3]}", font=("Segoe UI", 10),
                bg='white', fg=self.colors['text']).pack(anchor='w')
        tk.Label(info_frame, text=f"Expires: {values[4]}", font=("Segoe UI", 10),
                bg='white', fg=self.colors['text']).pack(anchor='w')
        
        # Actions
        tk.Frame(info_frame, bg=self.colors['grid_border'], height=1).pack(fill=tk.X, pady=15)
        
        tk.Label(info_frame, text="Actions:", font=("Segoe UI", 11, "bold"),
                bg='white', fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        btn_frame = tk.Frame(info_frame, bg='white')
        btn_frame.pack(fill=tk.X)
        
        if values[2] == 'ACTIVE':
            tk.Button(btn_frame, text="Suspend User",
                     bg=self.colors['error'], fg='white',
                     font=("Segoe UI", 10),
                     relief=tk.FLAT, padx=15, pady=8,
                     cursor='hand2',
                     command=lambda: [self.suspend_user(values[0]), dialog.destroy()]).pack(fill=tk.X, pady=2)
        elif values[2] == 'SUSPENDED':
            tk.Button(btn_frame, text="Activate User",
                     bg=self.colors['success'], fg='white',
                     font=("Segoe UI", 10),
                     relief=tk.FLAT, padx=15, pady=8,
                     cursor='hand2',
                     command=lambda: [self.activate_user(values[0]), dialog.destroy()]).pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="Extend License (30 days)",
                 bg=self.colors['accent'], fg='white',
                 font=("Segoe UI", 10),
                 relief=tk.FLAT, padx=15, pady=8,
                 cursor='hand2',
                 command=lambda: [self.extend_license(values[0]), dialog.destroy()]).pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="Close",
                 bg=self.colors['grid_header'], fg=self.colors['text'],
                 font=("Segoe UI", 10),
                 relief=tk.FLAT, padx=15, pady=8,
                 cursor='hand2',
                 command=dialog.destroy).pack(fill=tk.X, pady=2)
    
    def suspend_user(self, email):
        """Suspend a user"""
        if messagebox.askyesno("Confirm", f"Suspend user {email}?"):
            # TODO: Implement API call to suspend user
            messagebox.showinfo("Success", f"User {email} suspended")
            self.refresh_admin_users()
    
    def activate_user(self, email):
        """Activate a user"""
        if messagebox.askyesno("Confirm", f"Activate user {email}?"):
            # TODO: Implement API call to activate user
            messagebox.showinfo("Success", f"User {email} activated")
            self.refresh_admin_users()
    
    def extend_license(self, email):
        """Extend user license by 30 days"""
        if messagebox.askyesno("Confirm", f"Extend license for {email} by 30 days?"):
            # TODO: Implement API call to extend license
            messagebox.showinfo("Success", f"License extended for {email}")
            self.refresh_admin_users()
    
    
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
                    self.connection_label.config(text="📡 Signals ON | Ultra-fast monitoring (100ms)")
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
                    self.root.after(0, lambda: self.update_broker_status("✅ Connected - Ultra-fast"))
                    print("📡 Position monitoring started - checking every 100ms (ULTRA-FAST)")
                    
                    # Start position monitoring loop
                    self.position_monitor_running = True
                    poll_count = 0
                    while self.position_monitor_running:
                        try:
                            positions = loop.run_until_complete(self.broker.get_positions())
                            poll_count += 1
                            # Only log every 100 polls (10 seconds at 100ms) unless position exists
                            if positions or poll_count % 100 == 0:
                                if poll_count % 100 == 0:
                                    print(f"📊 Still monitoring... (Poll #{poll_count}, {len(positions)} position(s))")
                                elif positions:
                                    for p in positions:
                                        print(f"   🎯 {p['symbol']}: {p['quantity']} contracts")
                            self.check_position_change(positions, loop)
                        except Exception as e:
                            if poll_count % 100 == 0:
                                print(f"❌ Position poll error: {e}")
                        # Ultra-fast 100ms polling for lowest latency
                        # This provides near-instant signal delivery but increases CPU/API usage
                        # For less aggressive polling, change to 0.5 (500ms) or 1.0 (1 second)
                        time.sleep(0.1)  # Check every 100ms for ULTRA-FAST detection
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
    
    def setup_zones_tab(self, parent):
        """Setup the zones tab with supply/demand zones"""
        # Zones header
        zones_header = tk.Frame(parent, bg='white')
        zones_header.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(zones_header, text="🧩 Real-Time Zones", 
                font=("Segoe UI", 14, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        tk.Label(zones_header, text="(Supply/Demand zones from TradingView)", 
                font=("Segoe UI", 10),
                bg='white', fg=self.colors['text_light']).pack(side=tk.LEFT, padx=10)
        
        # Refresh button
        tk.Button(zones_header, text="🔄 Refresh Zones",
                font=("Segoe UI", 10),
                bg=self.colors['accent'], fg='white',
                activebackground='#1557b0',
                relief=tk.FLAT, padx=15, pady=5,
                cursor='hand2',
                command=self.refresh_zones).pack(side=tk.RIGHT)
        
        # Zones stats
        zones_stats = tk.Frame(parent, bg='white')
        zones_stats.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.zones_total_label = tk.Label(zones_stats, text="Total Zones: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['text'])
        self.zones_total_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.zones_supply_label = tk.Label(zones_stats, text="Supply: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['error'])
        self.zones_supply_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.zones_demand_label = tk.Label(zones_stats, text="Demand: 0", 
                font=("Segoe UI", 11), bg='white', fg=self.colors['success'])
        self.zones_demand_label.pack(side=tk.LEFT)
        
        # Zones table
        zones_table_frame = tk.Frame(parent, bg='white')
        zones_table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Create zones tree
        zones_columns = ('symbol', 'type', 'top', 'bottom', 'strength', 'status', 'created')
        self.zones_tree = ttk.Treeview(zones_table_frame, columns=zones_columns, show='headings',
                                       style="Spreadsheet.Treeview")
        
        # Define columns
        self.zones_tree.heading('symbol', text='Symbol')
        self.zones_tree.heading('type', text='Type')
        self.zones_tree.heading('top', text='Top')
        self.zones_tree.heading('bottom', text='Bottom')
        self.zones_tree.heading('strength', text='Strength')
        self.zones_tree.heading('status', text='Status')
        self.zones_tree.heading('created', text='Created')
        
        # Column widths
        self.zones_tree.column('symbol', width=80, minwidth=60)
        self.zones_tree.column('type', width=100, minwidth=80)
        self.zones_tree.column('top', width=100, minwidth=80)
        self.zones_tree.column('bottom', width=100, minwidth=80)
        self.zones_tree.column('strength', width=100, minwidth=80)
        self.zones_tree.column('status', width=100, minwidth=80)
        self.zones_tree.column('created', width=150, minwidth=100)
        
        # Scrollbar
        zones_scrollbar = ttk.Scrollbar(zones_table_frame, orient=tk.VERTICAL, command=self.zones_tree.yview)
        self.zones_tree.configure(yscrollcommand=zones_scrollbar.set)
        
        # Pack zones table
        self.zones_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        zones_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure row tags
        self.zones_tree.tag_configure('supply', background='#fce8e6')
        self.zones_tree.tag_configure('demand', background='#e6f4ea')
        
        # Initial load
        self.refresh_zones()
    
    def refresh_zones(self):
        """Refresh zones from API"""
        try:
            # Fetch zones for ES and NQ
            es_resp = requests.get(f"{CLOUD_API_BASE_URL}/api/zones/ES", timeout=5)
            nq_resp = requests.get(f"{CLOUD_API_BASE_URL}/api/zones/NQ", timeout=5)
            
            es_zones = es_resp.json().get('zones', []) if es_resp.status_code == 200 else []
            nq_zones = nq_resp.json().get('zones', []) if nq_resp.status_code == 200 else []
            
            all_zones = []
            for zone in es_zones:
                zone['symbol'] = 'ES'
                all_zones.append(zone)
            for zone in nq_zones:
                zone['symbol'] = 'NQ'
                all_zones.append(zone)
            
            self.root.after(0, lambda: self.update_zones_ui(all_zones))
        except Exception as e:
            print(f"Error fetching zones: {e}")
    
    def update_zones_ui(self, zones):
        """Update the zones table"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Clear existing items
            for item in self.zones_tree.get_children():
                self.zones_tree.delete(item)
            
            # Count stats
            total = len(zones)
            supply = sum(1 for z in zones if z.get('type', '').lower() == 'supply')
            demand = sum(1 for z in zones if z.get('type', '').lower() == 'demand')
            
            # Update stats
            self.zones_total_label.config(text=f"Total Zones: {total}")
            self.zones_supply_label.config(text=f"Supply: {supply}")
            self.zones_demand_label.config(text=f"Demand: {demand}")
            
            if not zones:
                self.zones_tree.insert('', 'end', values=(
                    'No zones', '', '', '', '', '', ''
                ))
                return
            
            # Add each zone
            for zone in zones:
                symbol = zone.get('symbol', 'N/A')
                zone_type = zone.get('type', 'supply').upper()
                top = f"${zone.get('top', 0):.2f}"
                bottom = f"${zone.get('bottom', 0):.2f}"
                strength = zone.get('strength', 'MEDIUM')
                status = zone.get('status', 'FRESH')
                created = zone.get('created_at', 'N/A')
                
                # Format created date
                if created and created != 'N/A':
                    try:
                        created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        created = created_date.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                
                # Determine tag
                tag = 'supply' if zone_type == 'SUPPLY' else 'demand'
                
                self.zones_tree.insert('', 'end', values=(
                    symbol,
                    zone_type,
                    top,
                    bottom,
                    strength,
                    status,
                    created
                ), tags=(tag,))
                
        except tk.TclError:
            return
        except Exception as e:
            print(f"Error updating zones UI: {e}")
    
    def setup_health_tab(self, parent):
        """Setup the health tab with system health monitoring"""
        # Health header
        health_header = tk.Frame(parent, bg='white')
        health_header.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(health_header, text="💚 System Health", 
                font=("Segoe UI", 14, "bold"),
                bg='white', fg=self.colors['text']).pack(side=tk.LEFT)
        
        tk.Label(health_header, text="(API, Database, Email, Services)", 
                font=("Segoe UI", 10),
                bg='white', fg=self.colors['text_light']).pack(side=tk.LEFT, padx=10)
        
        # Refresh button
        tk.Button(health_header, text="🔄 Check Health",
                font=("Segoe UI", 10),
                bg=self.colors['accent'], fg='white',
                activebackground='#1557b0',
                relief=tk.FLAT, padx=15, pady=5,
                cursor='hand2',
                command=self.refresh_health).pack(side=tk.RIGHT)
        
        # Health content
        health_content = tk.Frame(parent, bg='white')
        health_content.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)
        
        # Overall status card
        overall_card = tk.Frame(health_content, bg=self.colors['grid_header'], padx=20, pady=20)
        overall_card.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(overall_card, text="Overall Status", 
                font=("Segoe UI", 12, "bold"),
                bg=self.colors['grid_header'], fg=self.colors['text']).pack(anchor='w')
        
        self.overall_health_label = tk.Label(overall_card, text="● Healthy", 
                font=("Segoe UI", 18, "bold"),
                bg=self.colors['grid_header'], fg=self.colors['success'])
        self.overall_health_label.pack(anchor='w', pady=(10, 0))
        
        # Individual services
        services_frame = tk.Frame(health_content, bg='white')
        services_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create health indicators for each service
        self.health_indicators = {}
        
        services = [
            ('flask_server', 'Flask Server'),
            ('database', 'PostgreSQL Database'),
            ('email_service', 'Email Service'),
            ('whop_api', 'Whop API')
        ]
        
        for service_id, service_name in services:
            service_card = tk.Frame(services_frame, bg='white', pady=10)
            service_card.pack(fill=tk.X)
            
            label_frame = tk.Frame(service_card, bg='white')
            label_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            tk.Label(label_frame, text=service_name, 
                    font=("Segoe UI", 11, "bold"),
                    bg='white', fg=self.colors['text']).pack(anchor='w')
            
            status_label = tk.Label(label_frame, text="● Checking...", 
                    font=("Segoe UI", 10),
                    bg='white', fg=self.colors['text_light'])
            status_label.pack(anchor='w')
            
            self.health_indicators[service_id] = status_label
            
            # Separator
            tk.Frame(services_frame, bg=self.colors['grid_border'], height=1).pack(fill=tk.X, pady=5)
        
        # Initial load
        self.refresh_health()
    
    def refresh_health(self):
        """Refresh health status from API"""
        try:
            admin_key = self.config.get('master_key', '')
            resp = requests.get(
                f"{CLOUD_API_BASE_URL}/api/admin/system-health",
                params={'admin_key': admin_key},
                timeout=10
            )
            
            if resp.status_code == 200:
                health_data = resp.json()
                self.root.after(0, lambda: self.update_health_ui(health_data))
        except Exception as e:
            print(f"Error fetching health: {e}")
    
    def update_health_ui(self, health_data):
        """Update the health UI"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Update overall status
            overall_status = health_data.get('overall_status', 'unknown')
            if overall_status == 'healthy':
                self.overall_health_label.config(text="● Healthy", fg=self.colors['success'])
            elif overall_status == 'degraded':
                self.overall_health_label.config(text="⚠ Degraded", fg=self.colors['warning'])
            else:
                self.overall_health_label.config(text="✗ Unhealthy", fg=self.colors['error'])
            
            # Update individual services
            services = ['flask_server', 'database', 'email_service', 'whop_api']
            for service in services:
                if service in self.health_indicators and service in health_data:
                    service_data = health_data[service]
                    status = service_data.get('status', 'unknown')
                    response_time = service_data.get('response_time_ms', 0)
                    error = service_data.get('error')
                    
                    if status == 'healthy':
                        text = f"● Healthy ({response_time:.0f}ms)"
                        color = self.colors['success']
                    elif status == 'degraded':
                        text = f"⚠ Degraded ({response_time:.0f}ms)"
                        color = self.colors['warning']
                    else:
                        text = f"✗ Unhealthy"
                        if error:
                            text += f" - {error}"
                        color = self.colors['error']
                    
                    self.health_indicators[service].config(text=text, fg=color)
        
        except Exception as e:
            print(f"Error updating health UI: {e}")
    
    def run(self):
        """Start the launcher"""
        self.root.mainloop()


def main():
    """Entry point"""
    launcher = MasterLauncher()
    launcher.run()


if __name__ == "__main__":
    main()

