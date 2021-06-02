#!/usr/bin/python

from pathlib import Path
import subprocess
import logging
import logging.handlers
from re import match
import json
from os import environ, getuid, isatty
import traceback
from datetime import datetime
from typing import List, Iterator
from pacroller.utils import execute_with_io, UnknownQuestionError, back_readline, ask_interactive_question
from pacroller.checker import log_checker, sync_err_is_net, upgrade_err_is_net, checkReport
from pacroller.config import (CONFIG_DIR, CONFIG_FILE, LIB_DIR, DB_FILE, PACMAN_LOG, PACMAN_CONFIG,
                              TIMEOUT, UPGRADE_TIMEOUT, NETWORK_RETRY, CUSTOM_SYNC, SYNC_SH,
                              EXTRA_SAFE, SHELL, HOLD, NEEDRESTART, NEEDRESTART_CMD, SYSTEMD,
                              PACMAN_PKG_DIR, PACMAN_SCC, PACMAN_DB_LCK, SAVE_STDOUT, LOG_DIR)

logger = logging.getLogger()

class NonFatal(Exception):
    pass
class SyncRetry(NonFatal):
    pass
class MaxRetryReached(NonFatal):
    pass
class PackageHold(Exception):
    pass
class CheckFailed(Exception):
    pass
class NeedrestartFailed(Exception):
    pass

def sync() -> None:
    logger.info('sync start')
    if CUSTOM_SYNC:
        sync_cmd = [SHELL, SYNC_SH.resolve()]
    else:
        sync_cmd = ['pacman', '-Sy', '--noprogressbar', '--color', 'never']
    try:
        p = subprocess.run(
            sync_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            timeout=TIMEOUT,
            check=True
        )
    except subprocess.CalledProcessError as e:
        if sync_err_is_net(e.output):
            logger.warning('unable to download databases')
            raise SyncRetry()
        else:
            logger.exception(f'sync failed with {e.returncode=} {e.output=}')
            raise
    except subprocess.TimeoutExpired as e:
        logger.warning(f'database download timeout {e.timeout=} {e.output=}')
        if Path(PACMAN_DB_LCK).exists():
            logger.warning(f'automatically removing {PACMAN_DB_LCK}')
            Path(PACMAN_DB_LCK).unlink()
        raise SyncRetry()
    else:
        logger.debug(f'sync {p.stdout=}')
        logger.info('sync end')

def upgrade(interactive=False) -> List[str]:
    logger.info('upgrade start')
    check_upgrade_cmd = ['pacman', '-Qu', '--color', 'never']
    p = subprocess.run(
        check_upgrade_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8',
        timeout=TIMEOUT,
        check=False
    )
    if p.returncode != 1:
        p.check_returncode()
    upgrade_pkgs = list()
    for line in filter(None, p.stdout.split('\n')):
        pkgname, over, _ar, nver, *ignored = line.split()
        assert _ar == '->'
        assert not ignored or (len(ignored) == 1 and ignored[0] == "[ignored]")
        if ignored:
            logger.debug(f"upgrade ignored: {pkgname} {over} -> {nver}")
        else:
            logger.debug(f"upgrade: {pkgname} {over} -> {nver}")
            upgrade_pkgs.append((pkgname, over, nver))
    if not upgrade_pkgs:
        logger.info('upgrade end, nothing to do')
        exit(0)
    else:
        try:
            errors = list()
            for pkgname, over, nver in upgrade_pkgs:
                if _testreg := HOLD.get(pkgname):
                    _m_old = match(_testreg, over)
                    _m_new = match(_testreg, nver)
                    if _m_old and _m_new:
                        if (o := _m_old.groups()) != (n := _m_new.groups()):
                            errors.append(f"hold package {pkgname} is going to be upgraded from {o=} to {n=}")
                        if not o or not n:
                            errors.append(f"hold package {pkgname}: version regex missing matching groups {o=} {n=}")
                    else:
                        errors.append(f"cannot match version regex for hold package {pkgname}")
            if errors:
                raise PackageHold(errors)
        except PackageHold as e:
            if interactive:
                if ask_interactive_question(f"{e}, continue?"):
                    logger.warning("user determined to continue")
                else:
                    raise
            else:
                raise
    pacman_output = execute_with_io(['pacman', '-Su', '--noprogressbar', '--color', 'never'], UPGRADE_TIMEOUT, interactive=interactive)
    logger.info('upgrade end')
    return pacman_output

def do_system_upgrade(debug=False, interactive=False) -> checkReport:
    for _ in range(NETWORK_RETRY):
        try:
            sync()
        except SyncRetry:
            pass
        else:
            break
    else:
        raise MaxRetryReached(f'sync failed {NETWORK_RETRY} times')

    stdout_handler = None
    if SAVE_STDOUT:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            _formatter = logging.Formatter(fmt='%(asctime)s - %(message)s')
            stdout_handler = logging.handlers.RotatingFileHandler(LOG_DIR / "stdout.log", mode='a',
                            maxBytes=10*1024**2, backupCount=2)
            stdout_handler.setFormatter(_formatter)
            stdout_handler.setLevel(logging.DEBUG)
        except Exception:
            logging.exception(f"unable to save stdout to {LOG_DIR}")
            stdout_handler = None
    if stdout_handler:
        logger.addHandler(stdout_handler)

    for _ in range(NETWORK_RETRY):
        try:
            with open(PACMAN_LOG, 'r') as pacman_log:
                log_anchor = pacman_log.seek(0, 2)
            stdout = upgrade(interactive=interactive)
        except subprocess.CalledProcessError as e:
            if upgrade_err_is_net(e.output):
                logger.warning('upgrade download failed')
            else:
                raise
        else:
            break
    else:
        raise MaxRetryReached(f'upgrade failed {NETWORK_RETRY} times')

    if stdout_handler:
        logger.removeHandler(stdout_handler)

    with open(PACMAN_LOG, 'r') as pacman_log:
        pacman_log.seek(log_anchor)
        log = pacman_log.read().split('\n')
    try:
        report = log_checker(stdout, log, debug=debug)
    except Exception:
        logger.exception('checker has crashed, here is the debug info')
        logger.setLevel(logging.DEBUG)
        _report = log_checker(stdout, log, debug=True)
        raise

    logger.info(report.summary(verbose=True, show_package=False))
    return report

def write_db(report: checkReport, error: Exception = None) -> None:
    with open(LIB_DIR / DB_FILE, 'a') as db:
        db.write(json.dumps({'error': repr(error) if error else None, 'report': report.to_dict() if report else None}))
        db.write("\n")

def read_db() -> Iterator[dict]:
    if not (LIB_DIR / DB_FILE).exists():
        (LIB_DIR / DB_FILE).touch()
    with open(LIB_DIR / DB_FILE, 'rb') as db:
        for line in back_readline(db):
            if line:
                entry = json.loads(line)
                yield entry

def has_previous_error() -> str:
    for entry in read_db():
        return entry.get('error')
    else:
        return None

def is_system_failed() -> str:
    try:
        p = subprocess.run(["systemctl", "is-system-running"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        timeout=20,
                        encoding='utf-8',
                        check=False
        )
    except Exception:
        ret = "exec fail"
    else:
        ret = p.stdout.strip()
    if ret == 'running':
        return None
    else:
        return ret

def main() -> None:
    def locale_set() -> None:
        p = subprocess.run(['localectl', 'list-locales', '--no-pager'],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            encoding='utf-8',
                            timeout=20,
                            check=True
        )
        locales = [l.lower() for l in p.stdout.strip().split('\n')]
        preferred = ['en_US.UTF-8', 'C.UTF-8']
        for l in preferred:
            if l.lower() in locales:
                logger.debug(f'using locale {l}')
                environ['LANG'] = l
                break
        else:
            logger.debug('using fallback locale C')
            environ['LANG'] = 'C'
    def clear_pkg_cache() -> None:
        logger.debug('clearing package cache')
        for i in Path(PACMAN_PKG_DIR).iterdir():
            if i.is_file():
                i.unlink()
    def run_needrestart(ignore_error=False) -> None:
        logger.debug('running needrestart')
        try:
            p = subprocess.run(
                NEEDRESTART_CMD,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                timeout=TIMEOUT,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f'needrestart failed with {e.returncode=} {e.output=}')
            if not ignore_error:
                write_db(None, NeedrestartFailed(f'{e.returncode=}'))
            exit(2)
        else:
            logger.debug(f'needrestart {p.stdout=}')
    import argparse
    parser = argparse.ArgumentParser(description='Unattended Upgrades for Arch Linux')
    parser.add_argument('action', choices=['run', 'status', 'reset', 'fail-reset', 'reset-failed'],
                        help="what to do", metavar="run / status / reset ")
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose report')
    parser.add_argument('-m', '--max', type=int, default=1, help='Number of upgrades to show')
    parser.add_argument('-i', '--interactive', choices=['auto', 'on', 'off'],
                        default='auto', help='allow interactive questions',
                        metavar="auto / on / off ")
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    locale_set()
    interactive = args.interactive == "on" or not (args.interactive == 'off' or not isatty(0))
    logger.debug(f"interactive questions {'enabled' if interactive else 'disabled'}")

    if args.action == 'run':
        if getuid() != 0:
            logger.error('you need to be root')
            exit(1)
        if prev_err := has_previous_error():
            logger.error(f'Cannot continue, a previous error {prev_err} is still present. Please resolve this issue and run reset.')
            exit(2)
        if SYSTEMD:
            if _s := is_system_failed():
                logger.error(f'systemd is in {_s} state, refused')
                exit(11)
        if Path(PACMAN_DB_LCK).exists():
            logger.error(f'Database is locked at {PACMAN_DB_LCK}')
            exit(2)
        try:
            report = do_system_upgrade(debug=args.debug, interactive=interactive)
        except NonFatal:
            raise
        except Exception as e:
            write_db(None, e)
            raise
        else:
            exc = CheckFailed('manual inspection required') if report.failed else None
            write_db(report, exc)
            if exc:
                exit(2)
            if NEEDRESTART:
                run_needrestart()
            if PACMAN_SCC:
                clear_pkg_cache()

    elif args.action == 'status':
        count = 0
        failed = False
        for entry in read_db():
            if e := entry.get('error'):
                print(e)
                failed = True
            break
        for entry in read_db():
            if report_dict := entry.get('report'):
                count += 1
                report = checkReport(**report_dict)
                if not failed and count == 1:
                    failed = report.failed
                print(report.summary(verbose=args.verbose, show_package=True))
                if count >= args.max and args.max > 0:
                    break
                print()
        if failed:
            exit(2)
    elif args.action in {'reset', 'fail-reset', 'reset-failed'}:
        if getuid() != 0:
            logger.error('you need to be root')
            exit(1)
        try:
            subprocess.run(["systemctl", "is-failed", "pacroller"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        encoding='utf-8',
                        timeout=20,
                        check=True
            )
        except subprocess.CalledProcessError:
            pass
        else:
            subprocess.run(["systemctl", "reset-failed", "pacroller"], timeout=20, check=True)
        if SYSTEMD:
            if _s := is_system_failed():
                logger.error(f'systemd is in {_s} state, refused')
                exit(11)
        if prev_err := has_previous_error():
            write_db(None)
            logger.info(f'reset previous error {prev_err}')
            if NEEDRESTART:
                run_needrestart(True)
            if PACMAN_SCC:
                clear_pkg_cache()
        else:
            logger.warning('nothing to do')

if __name__ == '__main__':
    main()
