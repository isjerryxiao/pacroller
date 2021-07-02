import json
from pathlib import Path
import importlib.util
from base64 import b64decode
import sys
from typing import Any

CONFIG_DIR = Path('/etc/pacroller')
CONFIG_FILE = 'config.json'
CONFIG_FILE_SMTP = 'smtp.json'
F_KNOWN_OUTPUT_OVERRIDE = 'known_output_override.py'
LIB_DIR = Path('/var/lib/pacroller')
DB_FILE = 'db'
LOG_DIR = Path('/var/log/pacroller')
PACMAN_CONFIG = '/etc/pacman.conf'
PACMAN_LOG = '/var/log/pacman.log'
PACMAN_PKG_DIR = '/var/cache/pacman/pkg'
PACMAN_DB_LCK = '/var/lib/pacman/db.lck'
assert LIB_DIR.is_dir()

if (cfg := (CONFIG_DIR / CONFIG_FILE)).exists():
    _config: dict = json.loads(cfg.read_text())
else:
    _config = dict()

if (smtp_cfg := (CONFIG_DIR / CONFIG_FILE_SMTP)).exists():
    try:
        _smtp_cfg_text = smtp_cfg.read_text()
    except PermissionError:
        _smtp_config = dict()
    else:
        _smtp_config: dict = json.loads(_smtp_cfg_text)
else:
    _smtp_config = dict()

def _import_module(fpath: Path) -> Any:
    spec = importlib.util.spec_from_file_location(str(fpath).removesuffix('.py').replace('/', '.'), fpath)
    mod = importlib.util.module_from_spec(spec)
    _wbc = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    sys.dont_write_bytecode = _wbc
    return mod
if (_komf := (CONFIG_DIR / F_KNOWN_OUTPUT_OVERRIDE)).exists():
    _kom = _import_module(_komf.resolve())
    KNOWN_OUTPUT_OVERRIDE = (_kom.KNOWN_HOOK_OUTPUT, _kom.KNOWN_PACKAGE_OUTPUT)
else:
    KNOWN_OUTPUT_OVERRIDE = (dict(), dict())

TIMEOUT = int(_config.get('timeout', 300))
UPGRADE_TIMEOUT = int(_config.get('upgrade_timeout', 3600))
NETWORK_RETRY = int(_config.get('network_retry', 5))
assert TIMEOUT > 0 and UPGRADE_TIMEOUT > 0 and NETWORK_RETRY > 0

CUSTOM_SYNC = bool(_config.get('custom_sync', False))
SYNC_SH = CONFIG_DIR / str(_config.get('sync_shell', "sync.sh"))
if CUSTOM_SYNC:
    assert SYNC_SH.exists()

EXTRA_SAFE = bool(_config.get('extra_safe', False))
SHELL = str(_config.get('shell', '/bin/bash'))
SAVE_STDOUT = bool(_config.get('save_stdout', True))

HOLD = _config.get('hold', dict())
for (k, v)  in HOLD.items():
    assert isinstance(k, str) and isinstance(v, str)

IGNORED_PACNEW = _config.get('ignored_pacnew', list())
for i in IGNORED_PACNEW:
    assert isinstance(i, str)

NEEDRESTART = bool(_config.get('need_restart', False))
NEEDRESTART_CMD = _config.get('need_restart_cmd', ["needrestart", "-r", "a", "-m", "a", "-l"])
for i in NEEDRESTART_CMD:
    assert isinstance(i, str)

SYSTEMD = bool(_config.get('systemd-check', True))
PACMAN_SCC = bool(_config.get('clear_pkg_cache', False))

SMTP_ENABLED = bool(_smtp_config.get('enabled', False))
SMTP_SSL = bool(_smtp_config.get('ssl', True))
SMTP_HOST = _smtp_config.get('host', "")
SMTP_PORT = int(_smtp_config.get('port', 0))
SMTP_FROM = _smtp_config.get('from', "")
SMTP_TO = _smtp_config.get('to', "")
SMTP_AUTH = dict(_smtp_config.get('auth', {}))
if SMTP_ENABLED:
    assert SMTP_HOST
    assert SMTP_FROM
    assert SMTP_TO
    assert 0 <= SMTP_PORT <= 65536
    if SMTP_AUTH:
        assert SMTP_AUTH['username']
        if _smtp_auth_b64 := SMTP_AUTH.get('password_base64', ''):
            SMTP_AUTH['password'] = b64decode(_smtp_auth_b64).decode('utf-8')
            SMTP_AUTH.pop('password_base64')
        assert SMTP_AUTH['password']
        SMTP_AUTH = {k:v for k, v in SMTP_AUTH.items() if k in {'username', 'password'}}
