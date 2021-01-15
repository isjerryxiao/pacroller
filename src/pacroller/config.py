import json
from pathlib import Path

CONFIG_DIR = Path('/etc/pacroller')
CONFIG_FILE = 'config.json'
LIB_DIR = Path('/var/lib/pacroller')
DB_FILE = 'db'
PACMAN_CONFIG = '/etc/pacman.conf'
PACMAN_LOG = '/var/log/pacman.log'
assert LIB_DIR.is_dir()

if (cfg := (CONFIG_DIR / CONFIG_FILE)).exists():
    _config: dict = json.loads(cfg.read_text())
else:
    _config = dict()

UPGRADE_TIMEOUT = int(_config.get('upgrade_timeout', 3600))
NETWORK_RETRY = int(_config.get('network_retry', 5))
assert UPGRADE_TIMEOUT > 0 and NETWORK_RETRY > 0

CUSTOM_SYNC = bool(_config.get('custom_sync', False))
SYNC_SH = CONFIG_DIR / str(_config.get('sync_shell', "sync.sh"))
if CUSTOM_SYNC:
    assert SYNC_SH.exists()

EXTRA_SAFE = bool(_config.get('extra_safe', False))
SHELL = str(_config.get('shell', '/bin/bash'))

HOLD = _config.get('hold', dict())
for (k, v)  in HOLD.items():
    assert isinstance(k, str) and isinstance(v, str)

IGNORED_PACNEW = _config.get('ignored_pacnew', list())
assert isinstance(IGNORED_PACNEW, list)
