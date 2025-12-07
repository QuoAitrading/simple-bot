"""
Rainbow ASCII Art Logo for QuoTrading AI
Displays animated "QuoTrading AI" logo with rainbow colors that slowly transition
"""

import time
import sys
import os
import threading


# ANSI color codes for rainbow effect
class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Rainbow colors
    RED = '\033[91m'
    ORANGE = '\033[38;5;208m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    MAGENTA = '\033[35m'


# ASCII Art for "QUOTRADING AI" - Outline style that clearly spells the words
QUO_AI_LOGO = [
    "  ██████╗ ██╗   ██╗ ██████╗ ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗      █████╗ ██╗",
    " ██╔═══██╗██║   ██║██╔═══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝     ██╔══██╗██║",
    " ██║   ██║██║   ██║██║   ██║   ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗    ███████║██║",
    " ██║▄▄ ██║██║   ██║██║   ██║   ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║    ██╔══██║██║",
    " ╚██████╔╝╚██████╔╝╚██████╔╝   ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝    ██║  ██║██║",
    "  ╚═════╝  ╚═════╝  ╚═════╝    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝     ╚═╝  ╚═╝╚═╝"
]

# Compact bot ASCII art for session summary
BOT_ASCII_ART = [
    "     ___",
    "    /   \\",
    "   | o o |",
    "    \\___/",
    "   __|||__",
    "  |       |",
    "  | QUO   |",
    "  | TRADE |",
    "  |_______|",
    "   || | ||",
    "   || | ||",
]

# Subtitle for professional branding
SUBTITLE = "A L G O R I T H M I C   T R A D I N G"


def get_rainbow_colors():
    """Get list of rainbow colors in order"""
    return [
        Colors.RED,
        Colors.ORANGE,
        Colors.YELLOW,
        Colors.GREEN,
        Colors.CYAN,
        Colors.BLUE,
        Colors.PURPLE,
        Colors.MAGENTA
    ]


def color_char_with_gradient(char, position, total_chars, color_offset=0):
    """
    Color a single character based on its position in the line.
    Creates a rainbow gradient effect across the entire line.
    
    Args:
        char: Character to color
        position: Position of character in the line
        total_chars: Total characters in the line
        color_offset: Offset to shift the rainbow (for animation)
    
    Returns:
        Colored character string
    """
    if char.strip() == '':
        return char
    
    # Handle empty lines
    if total_chars == 0:
        return char
    
    rainbow = get_rainbow_colors()
    
    # Calculate which color to use based on position
    # Divide the line into segments, one for each color
    color_index = int((position / total_chars) * len(rainbow) + color_offset) % len(rainbow)
    color = rainbow[color_index]
    
    return f"{color}{char}{Colors.RESET}"


def color_line_with_gradient(line, color_offset):
    """
    Color a line with rainbow gradient.
    
    Args:
        line: Line of text to color
        color_offset: Offset for rainbow animation
    
    Returns:
        Colored line string
    """
    total_chars = len(line)
    colored_line = ""
    for i, char in enumerate(line):
        colored_line += color_char_with_gradient(char, i, total_chars, color_offset)
    return colored_line


def color_line_with_gradient_and_fade(line, color_offset, fade_progress):
    """
    Color a line with rainbow gradient and fade-in effect.
    Starts super dark and gradually becomes more visible.
    
    Args:
        line: Line of text to color
        color_offset: Offset for rainbow animation
        fade_progress: Progress of fade (0.0 = super dark, 1.0 = fully visible)
    
    Returns:
        Colored line string with fade effect
    """
    total_chars = len(line)
    colored_line = ""
    
    # Calculate brightness based on fade progress
    # Start at 0 (invisible/super dark) and go to 100 (fully visible)
    brightness = int(fade_progress * 100)
    
    # Use dim text ANSI code for fade effect
    if fade_progress < 0.3:
        # Super dark - use dark gray color
        dim_code = '\033[2m\033[90m'  # Dim + dark gray
    elif fade_progress < 0.6:
        # Medium - use regular gray
        dim_code = '\033[90m'  # Dark gray
    elif fade_progress < 0.9:
        # Getting visible - use light gray
        dim_code = '\033[37m'  # Light gray
    else:
        # Fully visible - use rainbow colors
        dim_code = ''
    
    if fade_progress < 0.9:
        # Apply dim effect during fade-in
        for char in line:
            if char.strip():
                colored_line += dim_code + char + Colors.RESET
            else:
                colored_line += char
    else:
        # Fully visible - use rainbow gradient
        for i, char in enumerate(line):
            colored_line += color_char_with_gradient(char, i, total_chars, color_offset)
    
    return colored_line


def display_logo_line(line, color_offset=0, center_width=80):
    """
    Display a single line of the logo with rainbow gradient, centered.
    
    Args:
        line: Line of ASCII art to display
        color_offset: Offset for rainbow animation
        center_width: Width to center the text within (default: 80)
    """
    colored_line = color_line_with_gradient(line, color_offset)
    
    # Center the line
    padding = (center_width - len(line)) // 2
    print(" " * padding + colored_line)


def display_animated_logo(duration=3.0, fps=20, with_headers=True, non_blocking=False, clear_after=False):
    """
    Display the QuoTrading AI logo with animated rainbow colors.
    Professional splash screen - shows logo with flowing rainbow gradient.
    Subtitle fades in from dark to visible over time.
    
    Args:
        duration: How long to display in seconds (default: 3.0, reduced for faster startup)
        fps: Frames per second for animation (default: 20, increased for smoother animation)
        with_headers: Whether to show header/footer text (default: True)
        non_blocking: If True, runs animation in background thread and returns immediately (default: False)
                     In non-blocking mode, animation displays and keeps updating at a fixed position
                     while allowing the main program to continue below
        clear_after: If True, clears the screen after animation completes (like a loading screen) (default: False)
    
    Returns:
        If non_blocking=True, returns the thread object. Otherwise returns None.
    """
    # If non_blocking mode, start animation in background and return immediately
    if non_blocking:
        
        def animate_continuously():
            """Run animation in background thread, continuously updating logo"""
            frames = int(duration * fps)
            delay = 1.0 / fps
            
            # Get terminal dimensions
            try:
                terminal_size = os.get_terminal_size()
                terminal_width = terminal_size.columns
            except OSError:
                terminal_width = 120
            
            # Calculate number of lines for logo
            total_lines = len(QUO_AI_LOGO) + 3  # Logo lines + blank + subtitle + blank
            
            # Display logo for first time and reserve space
            for i in range(total_lines):
                print()  # Reserve lines
            
            # Animate the logo in the reserved space
            for frame in range(frames):
                # Calculate color offset for flowing rainbow effect
                color_offset = (frame / frames) * len(get_rainbow_colors())
                
                # Calculate fade-in progress for subtitle (0.0 to 1.0)
                fade_progress = min(1.0, frame / max(1, frames * FADE_IN_PERCENTAGE))
                
                try:
                    # Move cursor to top of reserved space
                    # Use relative positioning: move up by total_lines
                    sys.stdout.write(f'\033[{total_lines}A')
                    
                    # Blank line at top
                    sys.stdout.write('\033[2K\n')
                    
                    # Display each line of logo with rainbow colors
                    for line in QUO_AI_LOGO:
                        sys.stdout.write('\033[2K')  # Clear line
                        colored_line = color_line_with_gradient(line, color_offset)
                        padding = max(0, (terminal_width - len(line)) // 2)
                        sys.stdout.write(" " * padding + colored_line + "\n")
                    
                    # Blank line
                    sys.stdout.write('\033[2K\n')
                    
                    # Subtitle with fade-in effect
                    sys.stdout.write('\033[2K')  # Clear line
                    subtitle_colored = color_line_with_gradient_and_fade(SUBTITLE, color_offset, fade_progress)
                    subtitle_padding = max(0, (terminal_width - len(SUBTITLE)) // 2)
                    sys.stdout.write(" " * subtitle_padding + subtitle_colored + "\n")
                    
                    # Blank line at bottom
                    sys.stdout.write('\033[2K\n')
                    
                    sys.stdout.flush()
                except (OSError, IOError):
                    # If terminal operations fail (e.g., output redirection), stop animation
                    break
                
                # Wait before next frame
                if frame < frames - 1:
                    time.sleep(delay)
        
        thread = threading.Thread(
            target=animate_continuously,
            daemon=True  # Daemon thread will not prevent program exit
        )
        thread.start()
        return thread
    
    # Blocking mode - original implementation
    frames = int(duration * fps)
    delay = 1.0 / fps
    
    # Get terminal dimensions for centering
    try:
        terminal_size = os.get_terminal_size()
        terminal_width = terminal_size.columns
        terminal_height = terminal_size.lines
    except OSError:
        # Terminal size cannot be determined (e.g., output redirected)
        terminal_width = 120
        terminal_height = 30
    
    # Calculate vertical centering - center the logo in the middle of screen
    logo_lines = len(QUO_AI_LOGO) + 2  # Logo + blank + subtitle
    vertical_padding = max(0, (terminal_height - logo_lines) // 2)
    
    # We'll update the display in place using carriage return and line clearing
    # Number of lines we'll be updating
    total_display_lines = len(QUO_AI_LOGO) + 2  # Logo + blank + subtitle
    
    for frame in range(frames):
        # Calculate color offset for flowing rainbow effect
        color_offset = (frame / frames) * len(get_rainbow_colors())
        
        # Calculate fade-in progress for subtitle (0.0 to 1.0)
        fade_progress = frame / max(1, frames - 1)
        
        # If first frame, add vertical padding to center logo
        if frame == 0:
            # Add top padding for vertical centering
            print("\n" * vertical_padding, end='')
            sys.stdout.flush()
        else:
            # Move cursor up to beginning of logo (not including top padding)
            sys.stdout.write(f'\033[{total_display_lines}A')
        
        # Display each line of logo with rainbow colors
        for line in QUO_AI_LOGO:
            # Clear the line first
            sys.stdout.write('\033[2K')
            # Get colored line and center it horizontally
            colored_line = color_line_with_gradient(line, color_offset)
            padding = max(0, (terminal_width - len(line)) // 2)
            sys.stdout.write(" " * padding + colored_line + "\n")
        
        # Blank line
        sys.stdout.write('\033[2K\n')
        
        # Subtitle with fade-in effect (centered)
        sys.stdout.write('\033[2K')  # Clear line
        # Apply rainbow gradient to subtitle with fade-in
        subtitle_colored = color_line_with_gradient_and_fade(SUBTITLE, color_offset, fade_progress)
        subtitle_padding = max(0, (terminal_width - len(SUBTITLE)) // 2)
        sys.stdout.write(" " * subtitle_padding + subtitle_colored + "\n")
        
        # Flush to ensure immediate display
        sys.stdout.flush()
        
        # Wait before next frame
        if frame < frames - 1:
            time.sleep(delay)
    
    # Clear screen or add spacing after logo
    if clear_after:
        # Clear screen like a loading screen in a video game
        # Use ANSI escape code to clear screen and move cursor to top
        sys.stdout.write('\033[2J')  # Clear entire screen
        sys.stdout.write('\033[H')   # Move cursor to home position (top-left)
        sys.stdout.flush()
    elif not with_headers:
        print("\n" * 2)
    else:
        print("\n" + "=" * 60)
        print(" " * 20 + "INITIALIZING...")
        print("=" * 60 + "\n")


def display_static_logo():
    """Display the logo without animation (single rainbow gradient)"""
    print()
    for line in QUO_AI_LOGO:
        display_logo_line(line, 0)
    print()


def get_rainbow_bot_art_with_message():
    """
    Get thank you message with rainbow colors for display on right side.
    Returns a list of colored strings, one per line.
    Simple text format without robot art.
    Vertically centered in the right margin space.
    """
    rainbow = get_rainbow_colors()
    colored_lines = []
    
    # Add blank lines to push message down to vertical center
    colored_lines.append("")
    colored_lines.append("")
    colored_lines.append("")
    colored_lines.append("")
    
    # Add rainbow-colored "Thanks for using QuoTrading AI"
    message = "Thanks for using QuoTrading AI"
    colored_message = ''.join(f"{rainbow[i % len(rainbow)]}{char}{Colors.RESET}" for i, char in enumerate(message))
    colored_lines.append(colored_message)
    
    # Add blank line
    colored_lines.append("")
    
    # Add support info on one line
    colored_lines.append("Any issues? Reach out to: support@quotrading.com")
    
    return colored_lines


# Thank you message constants
THANK_YOU_MESSAGE = "Thanks for using QuoTrading AI"
SUPPORT_MESSAGE = "Any issues? Reach out to: support@quotrading.com"

# Subtitle fades in during first 10% of animation
FADE_IN_PERCENTAGE = 0.1

# Welcome header constant - for startup rainbow animation
WELCOME_HEADER = "Welcome to QuoTrading AI Professional Trading System"


def display_animated_welcome_header(duration=10.0, fps=10, non_blocking=False):
    """
    Display rainbow "QuoTrading AI Professional Trading System" header with animation.
    Colors cycle through the text while it stays in place - exactly like thank you message.
    
    In blocking mode (recommended): Animates for the duration, then continues.
    In non-blocking mode: Displays static rainbow header (animation would conflict with bot output).
    
    Args:
        duration: How long to animate/display in seconds (default: 10.0)
        fps: Frames per second for animation (default: 10)
        non_blocking: If True, displays static header in background thread (default: False)
                     If False, animates synchronously like thank you message (recommended)
    
    Returns:
        If non_blocking=True, returns the thread object. Otherwise returns None.
    """
    # If non_blocking mode, display static rainbow header (non-animated)
    if non_blocking:
        def display_static_rainbow_header():
            """Display static rainbow header with rainbow-colored text"""
            rainbow = get_rainbow_colors()
            
            # Get terminal width for centering
            try:
                terminal_size = os.get_terminal_size()
                terminal_width = terminal_size.columns
            except OSError:
                terminal_width = 120
            
            # Calculate padding for centering the header
            msg_padding = max(0, (terminal_width - len(WELCOME_HEADER)) // 2)
            
            # Display the header with separators
            separator = "=" * 80
            sep_padding = max(0, (terminal_width - 80) // 2)
            
            try:
                # Print header with rainbow colors once (static, not animated)
                # Each character gets a different rainbow color based on position
                print()
                print(" " * sep_padding + separator)
                
                # Display header with rainbow-colored text (static)
                colored_header = ''.join(
                    f"{rainbow[i % len(rainbow)]}{char}{Colors.RESET}" 
                    for i, char in enumerate(WELCOME_HEADER)
                )
                print(" " * msg_padding + colored_header)
                
                print(" " * sep_padding + separator)
                print()
                
                # Keep thread alive for duration but don't animate
                # Animation would conflict with bot output
                time.sleep(duration)
                
            except (KeyboardInterrupt, OSError, IOError):
                pass
        
        thread = threading.Thread(
            target=display_static_rainbow_header,
            daemon=True
        )
        thread.start()
        return thread
    
    # Blocking mode - original implementation
    frames = int(duration * fps)
    delay = 1.0 / fps
    rainbow = get_rainbow_colors()
    
    # Get terminal width for centering
    try:
        terminal_size = os.get_terminal_size()
        terminal_width = terminal_size.columns
    except OSError:
        terminal_width = 120
    
    # Calculate padding for centering the header
    msg_padding = max(0, (terminal_width - len(WELCOME_HEADER)) // 2)
    
    # Display the header with separators
    separator = "=" * 80
    sep_padding = max(0, (terminal_width - 80) // 2)
    
    # Print initial frame with separators
    print()
    print(" " * sep_padding + separator)
    
    try:
        for frame in range(frames):
            # Calculate color offset for flowing rainbow effect
            color_offset = frame % len(rainbow)
            
            # Move cursor up to overwrite previous frame (just 1 line: the header)
            if frame > 0:
                sys.stdout.write('\033[1A')  # Move up 1 line
            
            # Clear line and display rainbow header with offset
            sys.stdout.write('\033[2K')  # Clear line
            colored_header = ''.join(
                f"{rainbow[(i + color_offset) % len(rainbow)]}{char}{Colors.RESET}" 
                for i, char in enumerate(WELCOME_HEADER)
            )
            sys.stdout.write(" " * msg_padding + colored_header + "\n")
            
            sys.stdout.flush()
            
            if frame < frames - 1:
                time.sleep(delay)
    except KeyboardInterrupt:
        # Allow graceful interruption without crashing
        # Print final separator and continue
        pass
    finally:
        # Always print closing separator, even if interrupted
        print(" " * sep_padding + separator)
        print()


def display_quick_rainbow_header(message=None, duration=2.0, fps=10):
    """
    Display a quick animated rainbow header with text.
    Colors cycle through the text for a brief animation effect.
    
    This is a lightweight, non-blocking alternative to display_animated_welcome_header.
    Perfect for startup headers that need visual appeal without long delays.
    
    Args:
        message: Text to display (default: WELCOME_HEADER)
        duration: How long to animate in seconds (default: 2.0 for quick startup)
        fps: Frames per second for animation (default: 10)
    """
    if message is None:
        message = WELCOME_HEADER
    
    frames = int(duration * fps)
    delay = 1.0 / fps
    rainbow = get_rainbow_colors()
    
    # Get terminal width for centering
    try:
        terminal_size = os.get_terminal_size()
        terminal_width = terminal_size.columns
    except OSError:
        terminal_width = 120
    
    # Calculate padding for centering the header
    msg_padding = max(0, (terminal_width - len(message)) // 2)
    
    # Display separator
    separator = "=" * 80
    sep_padding = max(0, (terminal_width - 80) // 2)
    
    print()
    print(" " * sep_padding + separator)
    
    # Display animated header
    for frame in range(frames):
        # Calculate color offset for flowing rainbow effect
        color_offset = frame % len(rainbow)
        
        # Move cursor up to overwrite previous frame (after first frame)
        # Combined ANSI escape sequences for better performance
        if frame > 0:
            sys.stdout.write('\033[1A\r\033[2K')  # Move up, return to start, clear line
        
        # Display rainbow header with offset
        colored_header = ''.join(
            f"{rainbow[(i + color_offset) % len(rainbow)]}{char}{Colors.RESET}" 
            for i, char in enumerate(message)
        )
        sys.stdout.write(" " * msg_padding + colored_header)
        
        # Add newline for cursor positioning
        sys.stdout.write('\n')
        sys.stdout.flush()
        
        # Sleep between frames (except after last frame)
        if frame < frames - 1:
            time.sleep(delay)
    
    # Print closing separator
    print(" " * sep_padding + separator)
    print()


def display_animated_thank_you(duration=60.0, fps=15):
    """
    Display animated rainbow "Thanks for using QuoTrading AI" message.
    Colors flow/cycle through the text for a smooth animation effect.
    
    Note: This function manipulates terminal cursor position to create animation.
    It overwrites previous output lines during the animation loop.
    
    Args:
        duration: How long to animate in seconds (default: 60.0)
        fps: Frames per second for animation (default: 15)
    """
    frames = int(duration * fps)
    delay = 1.0 / fps
    rainbow = get_rainbow_colors()
    
    # Get terminal width for centering
    try:
        terminal_size = os.get_terminal_size()
        terminal_width = terminal_size.columns
    except OSError:
        terminal_width = 80
    
    # Calculate padding for centering
    msg_padding = max(0, (terminal_width - len(THANK_YOU_MESSAGE)) // 2)
    support_padding = max(0, (terminal_width - len(SUPPORT_MESSAGE)) // 2)
    
    # Single blank line before starting (appears right after logout message)
    print()
    
    for frame in range(frames):
        # Calculate color offset for flowing rainbow effect
        color_offset = frame % len(rainbow)
        
        # Move cursor up to overwrite previous frame (2 lines: message + support)
        if frame > 0:
            sys.stdout.write('\033[2A')  # Move up 2 lines
        
        # Clear line and display rainbow message with offset
        sys.stdout.write('\033[2K')  # Clear line
        colored_message = ''.join(
            f"{rainbow[(i + color_offset) % len(rainbow)]}{char}{Colors.RESET}" 
            for i, char in enumerate(THANK_YOU_MESSAGE)
        )
        sys.stdout.write(" " * msg_padding + colored_message + "\n")
        
        # Display support line with same rainbow offset
        sys.stdout.write('\033[2K')  # Clear line
        colored_support = ''.join(
            f"{rainbow[(i + color_offset) % len(rainbow)]}{char}{Colors.RESET}" 
            for i, char in enumerate(SUPPORT_MESSAGE)
        )
        sys.stdout.write(" " * support_padding + colored_support + "\n")
        
        sys.stdout.flush()
        
        if frame < frames - 1:
            time.sleep(delay)
    
    # Final newline for spacing
    print()


def display_static_thank_you():
    """
    Display static rainbow "Thanks for using QuoTrading AI" message.
    Used as fallback when animation is not possible.
    """
    rainbow = get_rainbow_colors()
    
    # Color each character with rainbow gradient
    colored_message = ''.join(
        f"{rainbow[i % len(rainbow)]}{char}{Colors.RESET}" 
        for i, char in enumerate(THANK_YOU_MESSAGE)
    )
    colored_support = ''.join(
        f"{rainbow[i % len(rainbow)]}{char}{Colors.RESET}" 
        for i, char in enumerate(SUPPORT_MESSAGE)
    )
    
    print()
    print(colored_message)
    print()
    print(colored_support)
    print()


def get_rainbow_bot_art():
    """
    Get bot ASCII art with rainbow colors applied.
    Returns a list of colored strings, one per line.
    """
    rainbow = get_rainbow_colors()
    colored_lines = []
    
    for line_idx, line in enumerate(BOT_ASCII_ART):
        colored_line = ''
        for char_idx, char in enumerate(line):
            if char.strip():  # Only color non-whitespace characters
                color = rainbow[(line_idx + char_idx) % len(rainbow)]
                colored_line += f"{color}{char}{Colors.RESET}"
            else:
                colored_line += char
        colored_lines.append(colored_line)
    
    return colored_lines


if __name__ == "__main__":
    # Test the logo display
    print("Testing QuoTrading AI Rainbow Logo...")
    print("=" * 60)
    display_animated_logo(duration=5.0, fps=15)
    print("=" * 60)
    print("Logo test complete!")
