#!/usr/bin/python

from pacroller.config import PACMAN_LOG
from pacroller.checker import _log_parser, checkReport
from pacroller.utils import back_readline
import logging
import re

class _colors:
    TITLE = '\033[96m'
    PINK = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARN = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
class _nocolors:
    def __getattr__(self, attr: str) -> str:
        return ""
colors = _colors()
nocolors = _nocolors()

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Standalone Parsing Tool for pacman.log')
    parser.add_argument('-l', '--log-file', type=str, default=PACMAN_LOG, help='pacman log location')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose report')
    parser.add_argument('-n', '--number', type=int, default=0, help='which upgrade to parse')
    parser.add_argument('-m', '--max', type=int, default=1, help='max numbers of upgrade to parse')
    parser.add_argument('-p', '--no-package', action='store_true', help='do not show package changes')
    parser.add_argument('-c', '--no-color', action='store_true', help='do not show colors')
    args = parser.parse_args()
    args.number = args.number if args.number >= 0 else - args.number - 1

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()
    with open(args.log_file, "rb") as f:
        current_at = 0
        logs = list()
        log = list()
        for line in back_readline(f):
            if not line:
                continue
            (_, rsrc, msg) = line.split(' ', maxsplit=2)
            logger.debug(f"{rsrc=} {msg=}")
            if rsrc == "[PACMAN]":
                continue
            log.insert(0, line)
            if rsrc == "[ALPM]" and msg == "transaction started":
                current_at += 1
                if current_at < args.number + args.max + 1:
                    if current_at > args.number:
                        logs.append(log)
                        log = list()
                    else:
                        log.clear()
                else:
                    break
        else:
            if log:
                logs.append(log)
        for seq, log in enumerate(logs):
            logger.debug(f"report input {log=}")
            report = checkReport()
            _log_parser(log, report)
            c = nocolors if args.no_color else colors
            summary = report.summary(show_package=not args.no_package, verbose=args.verbose).split('\n')
            in_section = ""
            for i, line in enumerate(summary):
                if i == 0:
                    summary[i] = (f"{c.TITLE}=> Showing upgrade {c.PINK}{-args.number-1-seq}{c.ENDC}"
                                  f" started at{c.ENDC} {c.PINK}{log[0].split()[0].strip('[]')}{c.ENDC}")
                else:
                    if line[0] != ' ':
                        summary[i] = f"{c.GREEN}{line}{c.ENDC}"
                        in_section = line.strip()
                    else:
                        if not args.no_package and in_section == "Package changes:":
                            if args.verbose:
                                summary[i] = re.sub(f"(from|to) ([^ ]{{1,}})", f"\\1 {c.GREEN}\\2{c.ENDC}", summary[i])
                            for keyword in {"upgrade", "install", "remove"}:
                                if args.verbose:
                                    summary[i] = re.sub(f"({keyword}) ([^ ]{{1,}})", f"{c.PINK}\\1{c.ENDC} {c.BLUE}\\2{c.ENDC}", summary[i])
                                else:
                                    summary[i] = re.sub(f"({keyword}): (.*)", f"{c.PINK}\\1{c.ENDC} {c.BLUE}\\2{c.ENDC}", summary[i])
                        if in_section == "Collected Warnings:":
                            summary[i] = f"{c.WARN}{line}{c.ENDC}"
                            summary[i] = re.sub(f"(says|pacnew)", f"{c.ENDC}{c.BLUE}\\1{c.ENDC}{c.WARN}", summary[i])
                        elif in_section == "Collected Errors:":
                            summary[i] = f"{c.ERROR}{line}{c.ENDC}"
            print("\n".join(summary))

if __name__ == '__main__':
    main()
