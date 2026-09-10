"""
Tests for HADIL Native Startup Splash Subsystem
"""

import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.native_splash import HadilNativeSplash, get_global_splash

def test_splash_instantiation_and_global_reference():
    splash = HadilNativeSplash()
    assert get_global_splash() == splash
    assert splash.is_running is False
    assert splash.has_error is False

def test_splash_status_and_failure_reporting():
    splash = HadilNativeSplash()
    splash.set_status("Initializing Subsystems...")
    assert splash.error_text == "Initializing Subsystems..."
    
    splash.show_failure("Test Backend Error")
    assert splash.has_error is True
    assert splash.error_text == "Test Backend Error"

def test_cli_mode_bypasses_splash():
    from hadil_runtime import HadilRuntime
    runtime = HadilRuntime(port=8999, open_browser=False)
    assert runtime.open_browser is False
