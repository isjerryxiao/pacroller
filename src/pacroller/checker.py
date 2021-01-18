import logging
from typing import List, Tuple, Dict
from pathlib import Path
from re import compile, Pattern, match
from pacroller.utils import pacman_time_to_timestamp
from pacroller.known_output import KNOWN_HOOK_OUTPUT, KNOWN_PACKAGE_OUTPUT
from pacroller.config import IGNORED_PACNEW
from time import ctime, time

logger = logging.getLogger()

REGEX = {
    's_process_pkg_changes': r':: Processing package changes\.\.\.',
    's_post-transaction': r':: Running post-transaction hooks\.\.\.$',
    's_optdepend': r'(?i)(?:new )?optional dependencies for (.+)$',
    's_optdepend_list': r'    ([^:^ ]+).*',
    'l_running_hook': r'running \'(.+)\'\.\.\.',
    'l_transaction_start': r'transaction started',
    'l_transaction_complete': r'transaction completed',
    'l_upgrade': r'upgraded (.+) \((.+) -> (.+)\)',
    'l_install': r'installed (.+) \((.+)\)',
    'l_remove': r'removed (.+) \((.+)\)',
    'l_pacnew': r'warning: (.+) installed as (.+\.pacnew)',
}
for k, v in REGEX.items():
    REGEX[k] = compile(v)
REGEX: Dict[str, Pattern] # get through lint

class checkReport:
    def __init__(self, info: List[str] = None, warn: List[str] = None,
                 crit: List[str] = None, changes: List[Tuple[str]] = None,
                 date: int = int(time())) -> None:
        self._info = info or list()
        self._warn = warn or list()
        self._crit = crit or list()
        self._changes = changes or list()
        self._date = date
    @property
    def failed(self, extra_safe: bool = False) -> bool:
        if extra_safe:
            if self._info or self._warn or self._crit:
                return True
        else:
            if self._warn or self._crit:
                return True
        return False
    def to_dict(self) -> dict:
        return {'info': self._info, 'warn': self._warn, 'crit': self._crit, 'changes': self._changes, 'date': self._date}
    def summary(self, verbose=True, show_package=False, indent=2) -> str:
        ret = [f"Pacroller Report at {ctime(self._date)}",]
        if self._crit:
            ret.append("Collected Errors:")
            ret.extend([" " * indent + i for i in self._crit])
        if self._warn:
            ret.append("Collected Warnings:")
            ret.extend([" " * indent + i for i in self._warn])
        if verbose and self._info:
            ret.append("Collected Info:")
            ret.extend([" " * indent + i for i in self._info])
        if show_package:
            pkg_ret = list()
            installed = list()
            upgraded = list()
            removed = list()
            for c in self._changes:
                name, old, new = c
                if old and new:
                    upgraded.append(c)
                elif old is None:
                    installed.append(c)
                elif new is None:
                    removed.append(c)
                else:
                    raise RuntimeError(f"{c=}")
            if verbose:
                for c in upgraded:
                    name, old, new = c
                    pkg_ret.append(f'upgrade {name} from {old} to {new}')
                for c in installed:
                    name, _, new = c
                    pkg_ret.append(f'install {name} {new}')
                for c in removed:
                    name, old, _ = c
                    pkg_ret.append(f'remove {name} {old}')
            else:
                up, ins, rem = [[c[0] for c in x] for x in (upgraded, installed, removed)]
                if up:
                    pkg_ret.append(f'upgrade: {" ".join(up)}')
                if ins:
                    pkg_ret.append(f'install: {" ".join(ins)}')
                if rem:
                    pkg_ret.append(f'remove: {" ".join(rem)}')
            if pkg_ret:
                ret.append("Package changes:")
                ret.extend([" " * indent + i for i in pkg_ret])
        if len(ret) == 1:
            ret.append('nothing to show')
        return "\n".join(ret)
    def info(self, text: str) -> None:
        logger.debug(f'report info {text}')
        self._info.append(text)
    def warn(self, text: str) -> None:
        logger.debug(f'report warn {text}')
        self._warn.append(text)
    def crit(self, text: str) -> None:
        logger.debug(f'report crit {text}')
        self._crit.append(text)
    def change(self, name: str, old: str, new: str) -> None:
        logger.debug(f'report change {name=} {old=} {new=}')
        self._changes.append((name, old, new))

def log_checker(stdout: List[str], log: List[str], debug=False) -> checkReport:
    if debug:
        Path('/tmp/pacroller-stdout.log').write_text('\n'.join(stdout))
        Path('/tmp/pacroller-pacman.log').write_text('\n'.join(log))
    report = checkReport()
    _stdout_parser(stdout, report)
    _log_parser(log, report)
    return report

def _stdout_parser(stdout: List[str], report: checkReport) -> None:
    ln = 0
    in_package_change = False
    while ln < len(stdout):
        line = stdout[ln]
        if REGEX['s_process_pkg_changes'].match(line):
            in_package_change = True
            ln += 1
            continue
        elif REGEX['s_post-transaction'].match(line):
            in_package_change = False
            # we don't care anything below this
            logger.debug(f'break {line=}')
            break
        if in_package_change:
            if _m := REGEX['s_optdepend'].match(line):
                logger.debug(f'optdepend start {line=}')
                pkg = _m.groups()[0]
                optdeps = list()
                while True:
                    ln += 1
                    line = stdout[ln]
                    if _m := REGEX['s_optdepend_list'].match(line):
                        logger.debug(f'optdepend found {line=}')
                        optdeps.append(_m.groups()[0])
                    else:
                        logger.debug(f'optdepend end {line=}')
                        ln -= 1
                        break
                report.info(f'new optional dependencies for {pkg}: {", ".join(optdeps)}')
            else:
                logger.debug(f'stdout {line=} is unknown')
        else:
            logger.debug(f'skip {line=}')
        ln += 1

def _split_log_line(line: str) -> Tuple[int, str, str]:
    (time, source, msg) = line.split(' ', maxsplit=2)
    time: int = pacman_time_to_timestamp(time.strip('[]'))
    source = source.strip('[]')
    return (time, source, msg)
def _log_parser(log: List[str], report: checkReport) -> None:
    # preprocess
    if log[-1] == '':
        log = log[:-1]
    nlog = list()
    for line in log:
        try:
            _split_log_line(line)
            nlog.append(line)
        except Exception:
            logger.debug(f"preprocess logs: should not be on a new line, {line=}")
            assert nlog
            nlog[-1] = f"{nlog[-1]} {line}"
    log = nlog
    ln = 0
    in_transaction = 0
    while ln < len(log):
        line = log[ln]
        (_, source, msg) = _split_log_line(line)
        if source == 'PACMAN':
            pass # nothing concerning here
        elif source == 'ALPM':
            if _m := REGEX['l_upgrade'].match(msg):
                report.change(*(_m.groups()))
            elif _m := REGEX['l_install'].match(msg):
                name, new = _m.groups()
                report.change(name, None, new)
            elif _m := REGEX['l_remove'].match(msg):
                name, old = _m.groups()
                report.change(name, old, None)
            elif REGEX['l_transaction_start'].match(msg):
                logger.debug('transaction_start')
                if in_transaction == 0:
                    in_transaction = 1
                else:
                    report.crit(f'{ln=} duplicate transaction_start')
            elif REGEX['l_transaction_complete'].match(msg):
                logger.debug('transaction_complete')
                if in_transaction == 1:
                    in_transaction = 2
                else:
                    report.crit(f'{ln=} transaction_complete while {in_transaction=}')
            elif _m := REGEX['l_pacnew'].match(msg):
                orig, _ = _m.groups()
                if orig in IGNORED_PACNEW:
                    logger.debug(f'pacnew ignored for {orig}')
                else:
                    report.warn(f'please merge pacnew for {orig}')
            elif _m := REGEX['l_running_hook'].match(msg):
                hook_name = _m.groups()[0]
                logger.debug(f'hook start {hook_name=}')
                while True:
                    ln += 1
                    if ln >= len(log):
                        logger.debug(f'hook end {hook_name=} {msg=}')
                        ln -= 1
                        break
                    line = log[ln]
                    (_, source, msg) = _split_log_line(line)
                    if source == 'ALPM-SCRIPTLET':
                        for r in (*(KNOWN_HOOK_OUTPUT.get('', [])), *(KNOWN_HOOK_OUTPUT.get(hook_name, []))):
                            if match(r, msg):
                                logger.debug(f'hook output match {hook_name=} {msg=} {r=}')
                                break
                        else:
                            report.warn(f'hook {hook_name} says {msg}')
                    else:
                        logger.debug(f'hook end {hook_name=} {msg=}')
                        ln -= 1
                        break
            else:
                report.crit(f'ALPM {line=} is unknown')
        elif source == 'ALPM-SCRIPTLET':
            (_, _, _pmsg) = _split_log_line(log[ln-1])
            if _m := REGEX['l_upgrade'].match(_pmsg):
                pkg, *_ = _m.groups()
            elif _m := REGEX['l_install'].match(_pmsg):
                pkg, *_ = _m.groups()
            elif _m := REGEX['l_remove'].match(_pmsg):
                pkg, *_ = _m.groups()
            else:
                report.crit(f'{line=} has unknown SCRIPTLET output')
                ln += 1
                continue
            logger.debug(f'.install start {pkg=}')
            while True:
                line = log[ln]
                (_, source, msg) = _split_log_line(line)
                if source == 'ALPM-SCRIPTLET':
                    for r in (*(KNOWN_PACKAGE_OUTPUT.get('', [])), *(KNOWN_PACKAGE_OUTPUT.get(pkg, []))):
                        if match(r, msg):
                            logger.debug(f'.install output match {pkg=} {msg=} {r=}')
                            break
                    else:
                        report.warn(f'package {pkg} says {msg}')
                else:
                    logger.debug(f'.install end {pkg=} {msg=}')
                    ln -= 1
                    break
                ln += 1
        else:
            report.crit(f'{line=} has unknown source')
        ln += 1

def sync_err_is_net(output: str) -> bool:
    ''' check if a sync failure is caused by network '''
    output = output.strip().split('\n')
    if output[-1] == 'error: failed to synchronize all databases':
        return True
    else:
        return False
def upgrade_err_is_net(output: str) -> bool:
    ''' check if an upgrade failure is caused by network '''
    output = output.strip().split('\n')
    if len(output) >= 2 and 'warning: failed to retrieve some files' in output and \
       'error: failed to commit transaction (failed to retrieve some files)' in output:
        return True
    else:
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    stdout = Path('/tmp/pacroller-stdout.log').read_text().split('\n')
    log = Path('/tmp/pacroller-pacman.log').read_text().split('\n')
    report = checkReport()
    _stdout_parser(stdout, report)
    _log_parser(log, report)
    print(report.to_dict())
    print(report.summary(show_package=True, verbose=True))
