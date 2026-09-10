"""
HADIL Unified Runtime Launcher & Lifecycle Manager

Manages clean separation between:
1. Normal Desktop GUI Mode (Background Windows app + System Tray + Browser launcher + File logging)
2. CLI Interactive Mode (Visible terminal + Admin Console + Stdout logging)
"""

import sys
import os
import multiprocessing

def _log_diag(stage: str, msg: str = ""):
    try:
        proc_name = multiprocessing.current_process().name
        start_method = multiprocessing.get_start_method(allow_none=True)
        is_frozen = getattr(sys, 'frozen', False)
        exe = sys.executable
        pid = os.getpid()
        ppid = os.getppid() if hasattr(os, 'getppid') else -1
        args = sys.argv
        log_line = f"[{stage}] [PID:{pid}|PPID:{ppid}] [Proc:{proc_name}|StartMethod:{start_method}|Frozen:{is_frozen}] {msg} (Exe:{exe}, Args:{args})\n"
        print(log_line, end="", flush=True)
        log_dir = os.getenv("HADIL_DATA_DIR") or os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "HADIL")
        os.makedirs(log_dir, exist_ok=True)
        boot_log_file = os.path.join(log_dir, "hadil_boot.log")
        with open(boot_log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
            f.flush()
    except Exception as _e:
        pass

_log_diag("BOOT", "Top of backend/hadil_runtime.py reached")

# Critical PyInstaller / Windows Multiprocessing Intercept
# Must be called BEFORE any heavy application or AI/ML module imports
_log_diag("BOOT", "Calling multiprocessing.freeze_support()")
multiprocessing.freeze_support()
_log_diag("BOOT", "multiprocessing.freeze_support() returned")

def _is_cloud_startup() -> bool:
    mode = (os.getenv("HADIL_DEPLOYMENT_MODE") or "").strip().lower()
    if mode == "cloud":
        return True
    if mode == "desktop":
        return False
    return bool(os.getenv("RENDER"))

# Early Native Splash Launch for Packaged Desktop GUI Mode
# Must launch before heavy application / AI / ML module imports
_splash_instance = None
if multiprocessing.current_process().name == 'MainProcess' and sys.platform == 'win32' and not _is_cloud_startup():
    running_tests = (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or any("pytest" in arg or "unittest" in arg for arg in sys.argv)
    )
    if "--cli" not in sys.argv and "--admin" not in sys.argv and not running_tests:

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            from utils.native_splash import HadilNativeSplash
            _splash_instance = HadilNativeSplash()
            _splash_instance.start()
            _log_diag("SPLASH", "Native splash launched successfully")
        except Exception as _splash_err:
            _log_diag("SPLASH ERROR", f"Could not launch native splash: {_splash_err}")

import time
import logging
import threading
import socket
import webbrowser
import uvicorn
from typing import Optional

# Ensure parent directory is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

_log_diag("APP IMPORT", "Before importing routes.api")
import routes.api
_log_diag("APP IMPORT", "After importing routes.api")

_log_diag("APP IMPORT", "Before importing validators.sql_sanitizer")
import validators.sql_sanitizer
_log_diag("APP IMPORT", "After importing validators.sql_sanitizer")

_log_diag("APP IMPORT", "Before importing main.app")
from main import app
_log_diag("APP IMPORT", "After importing main.app")

_log_diag("APP IMPORT", "Before importing cli.admin_console")
from cli.admin_console import AdminConsole
_log_diag("APP IMPORT", "After importing cli.admin_console")

from utils.path_resolver import get_user_data_dir

logger = logging.getLogger(__name__)

# Global reference to active HadilRuntime instance for clean API trigger
_ACTIVE_RUNTIME: Optional["HadilRuntime"] = None

def get_active_runtime() -> Optional["HadilRuntime"]:
    return _ACTIVE_RUNTIME

def shutdown_active_runtime(delay_seconds: float = 0.0):
    """Gracefully shuts down the global HADIL runtime instance."""
    def _delayed_shutdown():
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        if _ACTIVE_RUNTIME:
            _ACTIVE_RUNTIME.shutdown()
    
    threading.Thread(target=_delayed_shutdown, daemon=True).start()

def find_free_port(starting_port: int = 8000, max_attempts: int = 100) -> int:
    """Finds an available local port starting from starting_port."""
    for p in range(starting_port, starting_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return starting_port

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if HADIL server is already actively listening on given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False

def ensure_console_attached():
    """
    Ensures a Windows console window is attached and STDIN/STDOUT/STDERR are bound to it.
    When packaged with console=False in PyInstaller, launching with --cli calls Win32 AllocConsole
    to dynamically spawn a dedicated interactive console window for stdin/stdout.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            # Check if process already has an attached console
            if ctypes.windll.kernel32.GetConsoleWindow() == 0:
                # Allocate a new console for this process
                if ctypes.windll.kernel32.AllocConsole():
                    # Reopen stdio channels to point to the newly allocated console device
                    sys.stdin = open("CONIN$", "r", encoding="utf-8")
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        except Exception as e:
            logger.warning(f"[HADIL RUNTIME] Could not allocate console: {e}")

class HadilLogStream:
    """
    Standard TextIO stream wrapper for sys.stdout and sys.stderr in windowless GUI runtime mode.
    Safely routes stdout and stderr writes into the persistent FileHandler log stream while
    providing standard stream methods (write, flush, isatty, encoding, errors).
    """
    def __init__(self, file_handler: logging.FileHandler, stream_name: str = "STDOUT"):
        self.file_handler = file_handler
        self.stream_name = stream_name
        self.encoding = "utf-8"
        self.errors = "replace"
        self.closed = False

    def write(self, s: str) -> int:
        if not s:
            return 0
        try:
            if self.file_handler and hasattr(self.file_handler, "stream") and self.file_handler.stream:
                self.file_handler.stream.write(s)
                self.file_handler.stream.flush()
        except Exception:
            pass
        return len(s)

    def flush(self) -> None:
        try:
            if self.file_handler and hasattr(self.file_handler, "stream") and self.file_handler.stream:
                self.file_handler.stream.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        return False

def configure_logging(cli_mode: bool):
    """
    Configures application logging.
    - CLI mode: attaches console if windowed, directs logs to stdout/console.
    - Normal mode: logs go to persistent log file %APPDATA%/HADIL/hadil_runtime.log
    """
    if cli_mode:
        ensure_console_attached()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    if cli_mode:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("[%(levelname)s] %(name)s - %(message)s")
        handler.setFormatter(fmt)
        root_logger.addHandler(handler)
    else:
        log_dir = get_user_data_dir()
        log_file = os.path.join(log_dir, "hadil_runtime.log")
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)
        
        # In normal mode, direct stdout/stderr to stream wrapper backed by file_handler log stream
        sys.stdout = HadilLogStream(file_handler, "STDOUT")
        sys.stderr = HadilLogStream(file_handler, "STDERR")



def create_tray_icon_image():
    """Generates an emerald HADIL icon for system tray if image asset is not on disk."""
    from PIL import Image, ImageDraw
    width = 64
    height = 64
    image = Image.new("RGBA", (width, height), (15, 22, 38, 255))
    dc = ImageDraw.Draw(image)
    # Outer emerald border circle
    dc.ellipse([4, 4, 60, 60], fill=(15, 22, 38), outline=(16, 185, 129), width=4)
    # Inner emerald diamond
    dc.polygon([(32, 16), (48, 32), (32, 48), (16, 32)], fill=(16, 185, 129))
    return image

class HadilServer(uvicorn.Server):
    """Custom Uvicorn Server wrapper allowing programmatically triggered shutdown."""
    def install_signal_handlers(self):
        pass

class HadilRuntime:
    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None, open_browser: bool = True):
        global _ACTIVE_RUNTIME
        _ACTIVE_RUNTIME = self

        self.host = host
        if port is None:
            configured_port = os.getenv("PORT")
            if configured_port:
                self.port = int(configured_port)
            else:
                self.port = find_free_port(8000)
        else:
            self.port = port
            
        self.open_browser = open_browser
        self.server: Optional[uvicorn.Server] = None
        self.server_thread: Optional[threading.Thread] = None
        self.fastapi_status = "STARTING"
        self.is_shutting_down = False
        self.tray_icon = None
        self.cli_mode = False

    def start_fastapi(self):
        _log_diag("SERVER THREAD", "start_fastapi: Entry point")
        try:
            _log_diag("SERVER THREAD", f"start_fastapi: Creating uvicorn.Config(app=app, host={self.host}, port={self.port}, log_config=None)")
            config = uvicorn.Config(
                app=app,
                host=self.host,
                port=self.port,
                log_level="info" if self.cli_mode else "warning",
                log_config=None
            )
            _log_diag("SERVER THREAD", "start_fastapi: Instantiating HadilServer")
            self.server = HadilServer(config=config)
            _log_diag("SERVER THREAD", "start_fastapi: Setting status to RUNNING")
            self.fastapi_status = "RUNNING"
            _log_diag("SERVER THREAD", "start_fastapi: Calling self.server.run()")
            self.server.run()
            _log_diag("SERVER THREAD", "start_fastapi: self.server.run() finished normally")
        except Exception as e:
            self.fastapi_status = "FAILED"
            _log_diag("SERVER THREAD EXCEPTION", f"Exception in start_fastapi: {e}")
            logger.exception(f"[HADIL RUNTIME ERROR] FastAPI server encountered exception in thread: {e}")
        finally:
            _log_diag("SERVER THREAD", "start_fastapi: Finally block executed")
            if not self.is_shutting_down:
                self.fastapi_status = "STOPPED"

    def get_fastapi_status(self) -> str:
        return self.fastapi_status

    def open_app_in_browser(self):
        app_url = f"http://{self.host}:{self.port}"
        try:
            logger.info(f"[HADIL RUNTIME] Opening browser at {app_url}")
            webbrowser.open(app_url)
        except Exception as e:
            logger.error(f"[HADIL RUNTIME] Failed to open browser: {e}")

    def restart(self):
        """Restarts the Uvicorn server and re-initializes runtime components."""
        logger.info("[HADIL RUNTIME] Restarting HADIL server...")
        if self.server:
            self.server.should_exit = True
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=3.0)
            
        self.is_shutting_down = False
        self.server_thread = threading.Thread(target=self.start_fastapi, daemon=True)
        self.server_thread.start()
        time.sleep(0.8)
        self.open_app_in_browser()
        logger.info("[HADIL RUNTIME] HADIL server restarted successfully.")

    def run_system_tray(self):
        """Creates and runs system tray icon in normal GUI mode."""
        _log_diag("TRAY", "Entering run_system_tray()")
        try:
            _log_diag("TRAY", "Importing pystray")
            import pystray
            _log_diag("TRAY", "Imported pystray successfully")
        except ImportError:
            _log_diag("TRAY", "pystray import failed")
            logger.warning("[HADIL RUNTIME] pystray not installed; skipping system tray creation.")
            return

        icon_img = create_tray_icon_image()

        def on_open(icon, item):
            self.open_app_in_browser()

        def on_restart(icon, item):
            threading.Thread(target=self.restart, daemon=True).start()

        def on_exit(icon, item):
            logger.info("[HADIL RUNTIME] Exit requested via System Tray menu.")
            if self.tray_icon:
                self.tray_icon.stop()
            self.shutdown()

        menu = pystray.Menu(
            pystray.MenuItem("Open HADIL", on_open, default=True),
            pystray.MenuItem("Restart HADIL", on_restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit HADIL", on_exit)
        )

        _log_diag("TRAY", "Creating pystray.Icon instance")
        self.tray_icon = pystray.Icon("HADIL", icon_img, "HADIL - Database Intelligence", menu)
        logger.info("[HADIL RUNTIME] System tray icon initialized.")
        _log_diag("TRAY", "Calling self.tray_icon.run()")
        self.tray_icon.run()
        _log_diag("TRAY", "self.tray_icon.run() returned")

    def start(self, cli_mode: bool = False):
        _log_diag("START 1", f"start() entered with cli_mode={cli_mode}")
        self.cli_mode = cli_mode
        
        _log_diag("START 2", "Before configure_logging()")
        configure_logging(cli_mode=cli_mode)
        _log_diag("START 3", "After configure_logging()")

        active_splash = None
        if not _is_cloud_startup():
            from utils.native_splash import get_global_splash
            active_splash = get_global_splash()

        if cli_mode and active_splash:
            active_splash.close()

        # Single instance check in normal mode
        if not cli_mode:
            _log_diag("START 4", "Before is_port_in_use() single instance check")
            port_active = is_port_in_use(self.port, self.host)
            _log_diag("START 5", f"After is_port_in_use() -> {port_active}")
            if port_active:
                if active_splash:
                    active_splash.close()
                app_url = f"http://{self.host}:{self.port}"
                logger.info(f"[HADIL RUNTIME] HADIL server already active at {app_url}. Bringing up browser.")
                if self.open_browser:
                    webbrowser.open(app_url)
                sys.exit(0)

        # 1. Start FastAPI server in background thread
        _log_diag("START 6", "Before Thread(target=self.start_fastapi)")
        self.server_thread = threading.Thread(target=self.start_fastapi, daemon=True)
        _log_diag("START 7", "After Thread creation, before self.server_thread.start()")
        self.server_thread.start()
        _log_diag("START 8", "After self.server_thread.start()")

        # Wait up to 15 seconds and poll whether Uvicorn server started and bound successfully
        server_started = False
        _log_diag("START 9", "Before polling loop for self.server.started")
        for i in range(150):
            if self.server and getattr(self.server, "started", False):
                server_started = True
                _log_diag("START 10", f"Detected server.started=True on iteration {i}")
                break
            if not self.server_thread.is_alive():
                _log_diag("START 11", f"server_thread died on iteration {i}")
                break
            time.sleep(0.1)

        _log_diag("START 12", f"Polling complete. server_started={server_started}")
        app_url = f"http://{self.host}:{self.port}"
        if server_started or is_port_in_use(self.port, self.host):
            self.fastapi_status = "RUNNING"
            logger.info(f"[HADIL RUNTIME] HADIL application running at {app_url}")
            if active_splash:
                active_splash.close()
        else:
            self.fastapi_status = "FAILED"
            logger.error(f"[HADIL RUNTIME ERROR] HADIL FastAPI server failed to start or bind on {app_url}. Check logs for details.")
            if active_splash:
                active_splash.show_failure("HADIL Backend Startup Failed.\nPlease check runtime logs.")

        if cli_mode:
            _log_diag("START 13", "Entering CLI mode branch")
            print("==================================================")
            print("[HADIL RUNTIME DIAGNOSTIC]")
            print(f"  Python executable:    {sys.executable}")
            print(f"  Hadil runtime file:   {os.path.abspath(__file__)}")
            print(f"  Port:                 {self.port}")
            print(f"  URL:                  {app_url}")
            print("==================================================")
            
            console = AdminConsole()
            try:
                console.main_menu(get_fastapi_status=self.get_fastapi_status)
            except (KeyboardInterrupt, SystemExit):
                logger.info("[HADIL RUNTIME] CLI interrupted.")
            finally:
                self.shutdown()
        else:
            _log_diag("START 14", "Entering GUI mode branch")
            if self.open_browser:
                _log_diag("START 15", "Before open_app_in_browser()")
                self.open_app_in_browser()
                _log_diag("START 16", "After open_app_in_browser()")

            # Run System Tray loop (blocking main thread cleanly)
            try:
                _log_diag("START 17", "Before run_system_tray()")
                self.run_system_tray()
                _log_diag("START 18", "After run_system_tray()")
            except Exception as e:
                _log_diag("START EXCEPTION", f"run_system_tray exception: {e}")
                logger.exception(f"[HADIL RUNTIME ERROR] System tray error: {e}")
                # Fallback wait loop if system tray fails
                while not self.is_shutting_down:
                    time.sleep(1.0)
            finally:
                _log_diag("START 19", "Calling self.shutdown()")
                self.shutdown()

    def shutdown(self):
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        _log_diag("BOOT", "shutdown() called")
        logger.info("[HADIL RUNTIME] Shutting down FastAPI server and cleaning up resources...")
        
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        if self.server:
            self.server.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=3.0)

        self.fastapi_status = "STOPPED"
        logger.info("[HADIL RUNTIME] Shutdown complete.")

def main():
    _log_diag("BOOT", "main() function entered")
    if _is_cloud_startup():
        from config.deployment import get_deployment_config
        cfg = get_deployment_config()
        cfg.validate_cloud_runtime()
        uvicorn.run(
            app,
            host=cfg.bind_host,
            port=cfg.bind_port,
            log_level="info",
        )
        return
    cli_mode = ("--cli" in sys.argv or "--admin" in sys.argv)
    host = os.getenv("HOST", "127.0.0.1")
    runtime = HadilRuntime(host=host)
    runtime.start(cli_mode=cli_mode)

if __name__ == "__main__":
    _log_diag("BOOT", "if __name__ == '__main__' block entered")
    main()
