"""
QuoTrading - Data Recorder Launcher
====================================
Standalone launcher for recording live market data for backtesting.

Features:
- Records live market data (quotes, trades, depth/DOM) for any ticker symbol
- Supports recording multiple symbols simultaneously
- Each symbol is saved to a separate CSV file for easy management
- Completely separate from the main trading system
- Ideal for collecting backtesting data

Data Captured:
- Quotes (Bid/Ask prices and sizes)
- Trades (Price, Size, Time)
- Market Depth/DOM (Order book levels)
- Timestamps (for synchronization)

Output Format:
- Separate CSV file per symbol (e.g., ES.csv, NQ.csv)
- Each file contains all data types for that symbol
- Chronologically ordered
- Ready for backtesting analysis
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import csv
from pathlib import Path
from datetime import datetime
import sys
import threading
import time
from typing import Dict, List, Any, Optional

# Add src directory to path for broker imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Configuration constants
RECORDER_CLEANUP_DELAY_SECONDS = 1  # Time to wait for recorder cleanup before exit


class DataRecorderLauncher:
    """GUI launcher for market data recording."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QuoTrading - Market Data Recorder")
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        
        # Professional color scheme
        self.colors = {
            'primary': '#E0E0E0',
            'secondary': '#D0D0D0',
            'success': '#0078D4',
            'success_dark': '#005A9E',
            'error': '#DC2626',
            'warning': '#F59E0B',
            'background': '#E0E0E0',
            'card': '#ECECEC',
            'text': '#1A1A1A',
            'text_light': '#3A3A3A',
            'text_secondary': '#5A5A5A',
            'border': '#0078D4',
            'border_subtle': '#BBBBBB',
            'input_bg': '#FFFFFF',
        }
        
        self.root.configure(bg=self.colors['background'])
        
        # Load/create config
        self.config_file = Path("data_recorder_config.json")
        self.config = self.load_config()
        
        # Recording state
        self.is_recording = False
        self.recorder_thread = None
        self.recorder = None
        
        # Rainbow animation state
        self.rainbow_colors = [
            '#FF0000', '#FF7F00', '#FFFF00', '#00FF00', 
            '#0000FF', '#4B0082', '#9400D3'
        ]
        self.current_color_index = 0
        self.animation_running = False
        self.animation_after_id = None  # Track animation callback ID
        
        # Show welcome screen first
        self.show_welcome_screen()
    
    def clear_widgets(self):
        """Clear all widgets from the window."""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def show_welcome_screen(self):
        """Display welcome screen with animated rainbow logo."""
        # Clear any existing widgets
        self.clear_widgets()
        
        # Set black background for welcome screen
        self.root.configure(bg='#000000')
        
        # Center frame
        center_frame = tk.Frame(self.root, bg='#000000')
        center_frame.place(relx=0.5, rely=0.4, anchor=tk.CENTER)
        
        # Animated welcome text
        self.welcome_label = tk.Label(
            center_frame,
            text="Welcome to QuoTrading AI Professional Trading System",
            font=("Segoe UI", 16, "bold"),
            bg='#000000',
            fg=self.rainbow_colors[0]
        )
        self.welcome_label.pack(pady=30)
        
        # Subtitle
        tk.Label(
            center_frame,
            text="Market Data Recorder",
            font=("Segoe UI", 12),
            bg='#000000',
            fg='#FFFFFF'
        ).pack(pady=10)
        
        # Launch button
        launch_button = tk.Button(
            center_frame,
            text="🚀 LAUNCH RECORDER",
            command=self.launch_recorder,
            font=("Segoe UI", 14, "bold"),
            bg='#0078D4',
            fg='white',
            relief=tk.FLAT,
            cursor="hand2",
            padx=40,
            pady=15,
            activebackground='#005A9E',
            activeforeground='white'
        )
        launch_button.pack(pady=30)
        
        # Start rainbow animation
        self.animation_running = True
        self.animate_rainbow()
    
    def animate_rainbow(self):
        """Animate the welcome text with rainbow colors."""
        if not self.animation_running:
            return
        
        try:
            if hasattr(self, 'welcome_label') and self.welcome_label.winfo_exists():
                # Cycle through rainbow colors
                self.current_color_index = (self.current_color_index + 1) % len(self.rainbow_colors)
                self.welcome_label.config(fg=self.rainbow_colors[self.current_color_index])
                
                # Continue animation (100ms = smooth color transition)
                self.animation_after_id = self.root.after(100, self.animate_rainbow)
        except tk.TclError:
            # Widget was destroyed, stop animation
            self.animation_running = False
    
    def launch_recorder(self):
        """Launch the main recorder interface."""
        # Stop animation
        self.animation_running = False
        
        # Cancel any pending animation callbacks
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        
        # Reset background color
        self.root.configure(bg=self.colors['background'])
        
        # Setup main UI
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Clear any existing widgets from welcome screen
        self.clear_widgets()
        
        # Header
        header = tk.Frame(self.root, bg=self.colors['success_dark'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="📊 Market Data Recorder",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['success_dark'],
            fg='white'
        ).pack(pady=(20, 2))
        
        tk.Label(
            header,
            text="Record live market data for backtesting",
            font=("Segoe UI", 9),
            bg=self.colors['success_dark'],
            fg='white'
        ).pack(pady=(0, 15))
        
        # Main content
        main = tk.Frame(self.root, bg=self.colors['background'], padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Broker credentials section
        cred_frame = tk.LabelFrame(
            main,
            text="Broker Credentials",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        cred_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Broker selection
        tk.Label(
            cred_frame,
            text="Broker:",
            font=("Segoe UI", 9),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.broker_var = tk.StringVar(value=self.config.get("broker", "TopStep"))
        broker_dropdown = ttk.Combobox(
            cred_frame,
            textvariable=self.broker_var,
            values=["TopStep"],
            state="readonly",
            font=("Segoe UI", 9),
            width=30
        )
        broker_dropdown.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        # Username
        tk.Label(
            cred_frame,
            text="Username:",
            font=("Segoe UI", 9),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.username_entry = tk.Entry(
            cred_frame,
            font=("Segoe UI", 9),
            bg=self.colors['input_bg'],
            width=32
        )
        self.username_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        self.username_entry.insert(0, self.config.get("broker_username", ""))
        
        # API Token
        tk.Label(
            cred_frame,
            text="API Token:",
            font=("Segoe UI", 9),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.token_entry = tk.Entry(
            cred_frame,
            font=("Segoe UI", 9),
            bg=self.colors['input_bg'],
            show="●",
            width=32
        )
        self.token_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        self.token_entry.insert(0, self.config.get("broker_token", ""))
        
        # Symbol selection section
        symbol_frame = tk.LabelFrame(
            main,
            text="Symbols to Record",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        symbol_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(
            symbol_frame,
            text="Select one or more symbols to record:",
            font=("Segoe UI", 9),
            bg=self.colors['card'],
            fg=self.colors['text_light']
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # Symbol checkboxes - Primary symbols for backtesting
        self.symbol_vars = {}
        symbols = [
            ("ES", "E-mini S&P 500"),
            ("MES", "Micro E-mini S&P 500"),
            ("NQ", "E-mini Nasdaq 100"),
            ("MNQ", "Micro E-mini Nasdaq 100"),
            ("GC", "Gold Futures"),
        ]
        
        symbol_grid = tk.Frame(symbol_frame, bg=self.colors['card'])
        symbol_grid.pack(fill=tk.X)
        
        saved_symbols = self.config.get("symbols", ["ES"])
        for i, (code, name) in enumerate(symbols):
            row = i // 2
            col = i % 2
            
            var = tk.BooleanVar(value=(code in saved_symbols))
            self.symbol_vars[code] = var
            
            cb = tk.Checkbutton(
                symbol_grid,
                text=f"{code} - {name}",
                variable=var,
                font=("Segoe UI", 9),
                bg=self.colors['card'],
                fg=self.colors['text']
            )
            cb.grid(row=row, column=col, sticky=tk.W, padx=10, pady=3)
        
        # Output settings section
        output_frame = tk.LabelFrame(
            main,
            text="Output Settings",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        output_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Output directory
        tk.Label(
            output_frame,
            text="Output Directory:",
            font=("Segoe UI", 9),
            bg=self.colors['card'],
            fg=self.colors['text']
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        file_frame = tk.Frame(output_frame, bg=self.colors['card'])
        file_frame.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        self.output_dir_var = tk.StringVar(
            value=self.config.get("output_dir", "market_data")
        )
        output_entry = tk.Entry(
            file_frame,
            textvariable=self.output_dir_var,
            font=("Segoe UI", 9),
            bg=self.colors['input_bg'],
            width=25
        )
        output_entry.pack(side=tk.LEFT)
        
        browse_btn = tk.Button(
            file_frame,
            text="Browse",
            command=self.browse_output_dir,
            font=("Segoe UI", 9),
            bg=self.colors['secondary'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Info label
        tk.Label(
            output_frame,
            text="Each symbol will be saved to a separate CSV file in this directory",
            font=("Segoe UI", 7),
            bg=self.colors['card'],
            fg=self.colors['text_secondary']
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Status section
        status_frame = tk.LabelFrame(
            main,
            text="Recording Status",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.status_text = tk.Text(
            status_frame,
            height=8,
            font=("Consolas", 9),
            bg='#1E1E1E',
            fg='#00FF00',
            state=tk.DISABLED
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        button_frame = tk.Frame(main, bg=self.colors['background'])
        button_frame.pack(fill=tk.X)
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ START RECORDING",
            command=self.start_recording,
            font=("Segoe UI", 11, "bold"),
            bg=self.colors['success'],
            fg='white',
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=12
        )
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        self.stop_button = tk.Button(
            button_frame,
            text="⬛ STOP RECORDING",
            command=self.stop_recording,
            font=("Segoe UI", 11, "bold"),
            bg=self.colors['error'],
            fg='white',
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=12,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        
        # Add status log
        self.log_message("Ready to record market data. Configure settings and click START.")
    
    def browse_output_dir(self):
        """Open directory browser for output directory selection."""
        directory = filedialog.askdirectory(
            initialdir=self.output_dir_var.get(),
            title="Select Output Directory"
        )
        if directory:
            self.output_dir_var.set(directory)
    
    def log_message(self, message: str):
        """Add message to status log."""
        self.status_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def start_recording(self):
        """Start recording market data."""
        # Validate inputs
        broker = self.broker_var.get()
        username = self.username_entry.get().strip()
        token = self.token_entry.get().strip()
        
        if not username or not token:
            messagebox.showerror(
                "Missing Credentials",
                "Please enter both username and API token."
            )
            return
        
        # Get selected symbols
        selected_symbols = [code for code, var in self.symbol_vars.items() if var.get()]
        if not selected_symbols:
            messagebox.showerror(
                "No Symbols Selected",
                "Please select at least one symbol to record."
            )
            return
        
        # Get output directory
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showerror(
                "No Output Directory",
                "Please specify an output directory."
            )
            return
        
        # Save config
        self.config["broker"] = broker
        self.config["broker_username"] = username
        self.config["broker_token"] = token
        self.config["symbols"] = selected_symbols
        self.config["output_dir"] = output_dir
        self.save_config()
        
        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_recording = True
        
        # Start recorder in background thread
        self.log_message(f"Starting data recorder for symbols: {', '.join(selected_symbols)}")
        self.log_message(f"Output directory: {output_dir}")
        
        self.recorder_thread = threading.Thread(
            target=self.run_recorder,
            args=(broker, username, token, selected_symbols, output_dir),
            daemon=True
        )
        self.recorder_thread.start()
    
    def run_recorder(self, broker: str, username: str, token: str, 
                     symbols: List[str], output_dir: str):
        """Run the data recorder (in background thread)."""
        try:
            # Import recorder
            from data_recorder import MarketDataRecorder
            
            # Create recorder
            self.recorder = MarketDataRecorder(
                broker=broker,
                username=username,
                api_token=token,
                symbols=symbols,
                output_dir=output_dir,
                log_callback=self.log_message
            )
            
            # Start recording
            self.recorder.start()
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"ERROR: {str(e)}"))
            self.root.after(0, self.stop_recording)
    
    def stop_recording(self):
        """Stop recording market data."""
        self.is_recording = False
        
        if self.recorder:
            self.log_message("Stopping recorder...")
            try:
                self.recorder.stop()
            except Exception as e:
                self.log_message(f"Error stopping recorder: {e}")
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log_message("Recording stopped.")
    
    def load_config(self) -> Dict:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def run(self):
        """Start the GUI application."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close event."""
        if self.is_recording:
            if messagebox.askyesno(
                "Recording in Progress",
                "Recording is still in progress. Stop recording and exit?"
            ):
                self.stop_recording()
                time.sleep(RECORDER_CLEANUP_DELAY_SECONDS)  # Give recorder time to clean up
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    app = DataRecorderLauncher()
    app.run()
