"""
AIMScribe Recorder - System Tray Application
Runs in background, receives triggers from CMED via localhost:5050
"""
import sys
import os
import asyncio
import logging
import threading
from datetime import datetime

import uvicorn
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from api.trigger_server import app, init_controller

# Setup logging
def setup_logging():
    """Configure logging"""
    os.makedirs(config.paths.logs_dir, exist_ok=True)

    log_file = os.path.join(
        config.paths.logs_dir,
        f"recorder_{datetime.now().strftime('%Y%m%d')}.log"
    )

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info(f"AIMScribe Recorder v{config.app_version} starting...")
    logger.info(f"Backend URL: {config.backend.base_url}")
    logger.info(f"AIMS LAB Server: {config.aimslab_server.base_url}")
    logger.info(f"Trigger Server: {config.trigger_server.host}:{config.trigger_server.port}")
    logger.info("=" * 60)

    return logger


def create_tray_icon():
    """Create system tray icon image"""
    # Create a simple icon (red circle for recording indicator)
    size = 64
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw a microphone-like icon (simplified)
    # Outer circle (green for ready)
    draw.ellipse([4, 4, size-4, size-4], fill=(76, 175, 80, 255))  # Green

    # Inner circle (white)
    inner_margin = 16
    draw.ellipse(
        [inner_margin, inner_margin, size-inner_margin, size-inner_margin],
        fill=(255, 255, 255, 255)
    )

    # Center dot (dark)
    center_margin = 24
    draw.ellipse(
        [center_margin, center_margin, size-center_margin, size-center_margin],
        fill=(33, 33, 33, 255)
    )

    return image


class RecorderTray:
    """System tray application"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.icon: Icon = None
        self.server_thread: threading.Thread = None
        self.running = True

    def create_menu(self):
        """Create tray menu"""
        return Menu(
            MenuItem("AIMScribe Recorder", None, enabled=False),
            MenuItem("─────────────", None, enabled=False),
            MenuItem("Status: Ready", self.on_status),
            MenuItem("─────────────", None, enabled=False),
            MenuItem("Open Logs", self.on_open_logs),
            MenuItem("─────────────", None, enabled=False),
            MenuItem("Exit", self.on_exit)
        )

    def on_status(self, icon, item):
        """Show status"""
        self.logger.info("Status checked via tray menu")

    def on_open_logs(self, icon, item):
        """Open logs folder"""
        import subprocess
        logs_path = os.path.abspath(config.paths.logs_dir)
        subprocess.Popen(f'explorer "{logs_path}"')

    def on_exit(self, icon, item):
        """Exit application"""
        self.logger.info("Exit requested via tray menu")
        self.running = False
        icon.stop()

    def run_server(self):
        """Run the FastAPI server in a separate thread"""
        # Initialize controller with backend and AIMS LAB server URLs
        init_controller(
            backend_url=config.backend.base_url,
            aimslab_server_url=config.aimslab_server.base_url
        )

        # Run uvicorn
        uvicorn.run(
            app,
            host=config.trigger_server.host,
            port=config.trigger_server.port,
            log_level="info"
        )

    def run(self):
        """Run the system tray application"""
        # Start server in background thread
        self.server_thread = threading.Thread(
            target=self.run_server,
            daemon=True,
            name="TriggerServerThread"
        )
        self.server_thread.start()

        self.logger.info(f"Trigger server started on {config.trigger_server.host}:{config.trigger_server.port}")

        # Create and run tray icon
        self.icon = Icon(
            name="AIMScribe Recorder",
            icon=create_tray_icon(),
            title="AIMScribe Recorder - Ready",
            menu=self.create_menu()
        )

        self.logger.info("System tray icon created")
        self.icon.run()


def main():
    """Main entry point"""
    logger = setup_logging()

    try:
        # Check dependencies
        try:
            import pyaudio
            import aiohttp
            import pystray
            from PIL import Image
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            print(f"Error: Missing dependency - {e}")
            print("Install with: pip install -r requirements.txt")
            sys.exit(1)

        # Run tray application
        tray = RecorderTray()
        tray.run()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
