import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

# Force UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

console = Console()

BANNER = r"""
  _ _              _       _        _             
 (_) |_ ___  _ __ | |_   _| |_ __ _| | _____  ___ 
 | | __/ _ \| '_ \| | | | | __/ _` | |/ / _ \/ __|
 | | || (_) | | | | | |_| | || (_| |   <  __/\__ \
 |_|\__\___/|_| |_|_|\__, |\__\__,_|_|\_\___||___/
                     |___/                        
"""

def print_boot_banner():
    """Displays the underground ASCII branding banner on startup."""
    console.clear()
    banner_text = Text(BANNER, style="bold cyan")
    subtitle = Text("\nGachapon Predictive Farmer & O.C.R. Sniper", style="bold white")
    footer = Text("\n[ Distribution: github.com/itonlytakes ]", style="dim cyan")
    
    panel_content = Text.assemble(banner_text, subtitle, footer)
    console.print(Panel(panel_content, border_style="cyan", expand=False))

def setup_logging() -> logging.Logger:
    """Configures Rich terminal output alongside rotating file logs."""
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger("UserBot")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Persistent File Handler (Debug level for troubleshooting)
    file_handler = RotatingFileHandler(
        "logs/userbot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Rich Console Handler (Info level for clean terminal visuals)
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        markup=True,
        log_time_format="[%X]"
    )
    rich_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(rich_handler)
    
    return logger