"""Installed program resources are immutable; user data survives upgrades."""
import os
import sys
from pathlib import Path

VERSION = '4.3.4'
PACKAGED = bool(getattr(sys, 'frozen', False))
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

def install_root():
    return Path(os.environ.get('CRUCES_INSTALL_ROOT', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Cruces'))

def data_dir():
    override = os.environ.get('CRUCES_DATA_DIR')
    path = Path(override) if override else install_root() / 'datos' if PACKAGED else RESOURCE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path

def extension_dir():
    return install_root() / 'lector' if PACKAGED else RESOURCE_DIR / 'bet365_extension'
