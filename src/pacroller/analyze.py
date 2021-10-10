#!/usr/bin/python

from pacroller.config import PACMAN_LOG
from pacroller.checker import _log_parser, checkReport
from pacroller.utils import back_readline
import logging

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Standalone Parsing Tool for pacman.log')
    parser.add_argument('-l', '--log-file', type=str, default=PACMAN_LOG, help='pacman log location')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose report')
    parser.add_argument('-n', '--number', type=int, default=0, help='which upgrade to parse')
    parser.add_argument('-p', '--no-package', action='store_true', help='do not show package changes')
    args = parser.parse_args()
    args.number = args.number if args.number >= 0 else - args.number - 1

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()
    with open(args.log_file, "rb") as f:
        current_at = 0
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
                if current_at > args.number:
                    break
                else:
                    log.clear()
        else:
            logger.info("number out of bound")
            log.clear()
        if log:
            report = checkReport()
            _log_parser(log, report)
            print(report.summary(show_package=not args.no_package, verbose=args.verbose))

if __name__ == '__main__':
    main()
