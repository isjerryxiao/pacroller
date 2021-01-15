#!/usr/bin/python

from pathlib import Path
import subprocess
import logging
from re import match
import json
from os import environ
import traceback
import pyalpm
import pycman
from typing import List, Iterator
from pacroller.utils import execute_with_io, UnknownQuestionError, back_readline
from pacroller.checker import log_checker, sync_err_is_net, upgrade_err_is_net, checkReport
from pacroller.config import (CONFIG_DIR, CONFIG_FILE, LIB_DIR, DB_FILE, PACMAN_LOG, PACMAN_CONFIG,
                              UPGRADE_TIMEOUT, NETWORK_RETRY, CUSTOM_SYNC, SYNC_SH, EXTRA_SAFE, SHELL, HOLD)

logger = logging.getLogger()

environ['LANG'] = 'en_US.utf8' # required for parsing

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
            timeout=300
        )
    except subprocess.CalledProcessError as e:
        if sync_err_is_net(e.output):
            logger.warning('unable to download databases')
            raise SyncRetry()
        else:
            logger.exception(f'sync failed with {e.returncode=} {e.output=}')
            raise
    else:
        logger.debug(f'sync {p.stdout=}')
        logger.info('sync end')

class alpmCallback:
    @staticmethod
    def noop() -> None:
        pass
    def setup_hdl(self, handle: pyalpm.Handle) -> None:
        handle.dlcb = self.noop
        handle.eventcb = self.noop
        handle.questioncb = self.noop
        handle.progresscb = self.noop

def upgrade() -> List[str]:
    logger.info('upgrade start')
    handle = pycman.config.init_with_config(PACMAN_CONFIG)
    localdb = handle.get_localdb()
    alpmCallback().setup_hdl(handle)
    t = handle.init_transaction()
    try:
        t.sysupgrade(False) # no downgrade
        if len(t.to_add) + len(t.to_remove) == 0:
            logger.info('upgrade end, nothing to do')
        else:
            def examine_upgrade(toadd: List[pyalpm.Package], toremove: List[pyalpm.Package]) -> None:
                for pkg in toadd:
                    localpkg: pyalpm.Package = localdb.get_pkg(pkg.name)
                    localver = localpkg.version if localpkg else ""
                    logger.debug(f"will upgrade {pkg.name} from {localver} to {pkg.version}")
                    if _testreg := HOLD.get(pkg.name):
                        _m_old = match(_testreg, localver)
                        _m_new = match(_testreg, pkg.version)
                        if _m_old and _m_new:
                            if (o := _m_old.groups()) != (n := _m_new.groups()):
                                raise PackageHold(f"hold package {pkg.name} is going to be upgraded from {o=} to {n=}")
                        else:
                            raise PackageHold(f"cannot match version regex for hold package {pkg.name}")
                for pkg in toremove:
                    logger.debug(f"will remove {pkg.name} version {pkg.version}")
                    if pkg.name in HOLD:
                        raise PackageHold(f"attempt to remove {pkg.name} which is set to hold")
            examine_upgrade(t.to_add, t.to_remove)
    finally:
        t.release()
    pacman_output = execute_with_io(['pacman', '-Su', '--noprogressbar', '--color', 'never'])
    logger.info('upgrade end')
    return pacman_output

def do_system_upgrade(debug=False) -> checkReport:
    for _ in range(NETWORK_RETRY):
        try:
            sync()
        except SyncRetry:
            pass
        else:
            break
    else:
        raise MaxRetryReached(f'sync failed {NETWORK_RETRY} times')

    for _ in range(NETWORK_RETRY):
        try:
            with open(PACMAN_LOG, 'r') as pacman_log:
                log_anchor = pacman_log.seek(0, 2)
            stdout = upgrade()
        except subprocess.CalledProcessError as e:
            if upgrade_err_is_net(e.output):
                logger.warning('upgrade download failed')
            else:
                raise
        else:
            break
    else:
        raise MaxRetryReached(f'upgrade failed {NETWORK_RETRY} times')

    with open(PACMAN_LOG, 'r') as pacman_log:
        pacman_log.seek(log_anchor)
        log = pacman_log.read().split('\n')
    report = log_checker(stdout, log, debug=debug)
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

def has_previous_error() -> Exception:
    for entry in read_db():
        return entry.get('error')
    else:
        return None

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Pacman Automatic Rolling Helper')
    parser.add_argument('action', choices=['run', 'status', 'fail-reset'])
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose report')
    parser.add_argument('-m', '--max', type=int, default=1, help='Number of upgrades to show')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    if args.action == 'run':
        if prev_err := has_previous_error():
            logger.error(f'Cannot continue, a previous error {prev_err} is still present. Please resolve this issue and run fail-reset.')
        else:
            try:
                report = do_system_upgrade(args.debug)
            except NonFatal:
                raise
            except Exception as e:
                write_db(None, e)
                raise
            else:
                exc = None
                if EXTRA_SAFE:
                    if report._info or report._warn or report._crit:
                        exc = CheckFailed('manual inspection required')
                else:
                    if report._warn or report._crit:
                        exc = CheckFailed('manual inspection required')
                write_db(report, exc)
    elif args.action == 'status':
        count = 0
        for entry in read_db():
            if report_dict := entry.get('report'):
                count += 1
                report = checkReport(**report_dict)
                print(report.summary(verbose=args.verbose, show_package=True))
                if count >= args.max:
                    break
                print()
    elif args.action == 'fail-reset':
        if prev_err := has_previous_error():
            write_db(None)
            logger.info(f'reset previous error {prev_err}')
        else:
            logger.warning('nothing to do')

if __name__ == '__main__':
    main()
