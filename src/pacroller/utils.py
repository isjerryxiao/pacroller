import subprocess
from threading import Thread
import logging
from typing import List, BinaryIO, Iterator, Union, Callable
from io import DEFAULT_BUFFER_SIZE
from time import mktime
from datetime import datetime
from signal import SIGINT, SIGTERM, Signals
from select import select
from sys import stdin
from os import set_blocking, close as os_close
from pty import openpty
from re import compile
logger = logging.getLogger()

ANSI_ESCAPE = compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
# https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
# 0a, 0d and 1b need special process
GENERAL_NON_PRINTABLE = {b'\x07', b'\x08', b'\x09', b'\x0b', b'\x0c', b'\x7f'}

class UnknownQuestionError(subprocess.SubprocessError):
    def __init__(self, question, output=None):
        self.question = question
        self.output = output
    def __str__(self):
        return f"Pacman returned an unknown question {self.question}"

def execute_with_io(command: List[str], timeout: int = 3600, interactive: bool = False) -> List[str]:
    '''
        captures stdout and stderr and
        automatically handles [y/n] questions of pacman
    '''
    def terminate(p: subprocess.Popen, timeout: int = 30, signal: Signals = SIGTERM) -> None:
        p.send_signal(signal)
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.critical(f'unable to terminate {p}, killing')
            p.kill()
    def set_timeout(p: subprocess.Popen, timeout: int, callback: Callable = lambda: None) -> None:
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.exception(f'{timeout=} expired for {p}, terminating')
            terminate(p)
        else:
            logger.debug('set_timeout exit')
        finally:
            callback()
    ptymaster, ptyslave = openpty()
    set_blocking(ptymaster, False)
    stdout = open(ptymaster, "rb", buffering=0)
    stdin = open(ptymaster, "w")
    p = subprocess.Popen(
            command,
            stdin=ptyslave,
            stdout=ptyslave,
            stderr=ptyslave,
    )
    logger.log(logging.DEBUG+1, f"running {command}")
    try:
        def cleanup():
            actions = (
                (stdin, "close"),
                (stdout, "close"),
                (ptymaster, os_close),
                (ptyslave, os_close),
            )
            for obj, action in actions:
                try:
                    if isinstance(action, str):
                        getattr(obj, action)()
                    else:
                        action(obj)
                except OSError:
                    pass
        Thread(target=set_timeout, args=(p, timeout, cleanup), daemon=True).start()
        output = ''
        SHOW_CURSOR, HIDE_CURSOR = '\x1b[?25h', '\x1b[?25l'
        while p.poll() is None:
            try:
                select([ptymaster], list(), list())
                _raw = stdout.read()
            except (OSError, ValueError):
                # should be cleanup routine closed the fd, lets check the process return code
                continue
            if not _raw:
                logger.debug('read void from stdout')
                continue
            logger.debug(f"raw stdout: {_raw}")
            for b in GENERAL_NON_PRINTABLE:
                _raw = _raw.replace(b, b'')
            raw = _raw.decode('utf-8', errors='replace')
            raw = raw.replace('\r\n', '\n').replace(HIDE_CURSOR, '')
            rawl = raw.split('\n')
            if output and output[-1] != '\n':
                rawl[0] = output[output.rfind('\n')+1:] + rawl[0]
            output += raw
            for l in rawl[:-1]:
                l = ANSI_ESCAPE.sub('', l)
                logger.log(logging.DEBUG+1, 'STDOUT: %s', l)
            rstrip1 = lambda x: x[:-1] if x.endswith(' ') else x
            rstrip_cursor = lambda s: rstrip1(s[:-len(SHOW_CURSOR)]) if s.endswith(SHOW_CURSOR) else f"{s}<no show cursor>"
            for l in rawl:
                line = rstrip_cursor(l)
                if line == ':: Proceed with installation? [Y/n]':
                    need_attention = False
                    stdin.write('y\n')
                    stdin.flush()
                elif line.lower().endswith('[y/n]') or line == 'Enter a number (default=1):':
                    need_attention = False
                    if interactive:
                        choice = ask_interactive_question(line, info=output)
                        if choice is None:
                            terminate(p, signal=SIGINT)
                            raise UnknownQuestionError(line, output)
                        elif choice:
                            stdin.write(f"{choice}\n")
                            stdin.flush()
                    else:
                        terminate(p, signal=SIGINT)
                        raise UnknownQuestionError(line, output)
    except (KeyboardInterrupt, UnknownQuestionError):
        terminate(p, signal=SIGINT)
        raise
    except Exception:
        terminate(p)
        raise
    if (ret := p.wait()) != 0:
        raise subprocess.CalledProcessError(ret, command, output)
    output = ANSI_ESCAPE.sub('', output)
    return output.split('\n')

def pacman_time_to_timestamp(stime: str) -> int:
    ''' the format pacman is using seems to be not iso compatible '''
    dt = datetime.strptime(stime, "%Y-%m-%dT%H:%M:%S%z")
    return mktime(dt.astimezone().timetuple())

def back_readline(fp: BinaryIO) -> Iterator[str]:
    pos = fp.seek(0, 2)
    if pos == 0:
        return
    previous = b''
    while pos > 0:
        next = max(pos - DEFAULT_BUFFER_SIZE, 0)
        fp.seek(next)
        got = fp.read(pos - next)
        got = got + previous
        blines = got.split(b'\n')
        while len(blines) > 1:
            yield blines.pop(-1).decode('utf-8')
        previous = blines[0]
        pos = next
    yield blines.pop(-1).decode('utf-8')

def ask_interactive_question(question: str = "", timeout: int = 60, info: str = "") -> Union[str, None]:
    ''' on timeout, returns None '''
    if info:
        print(info)
    print(f"Please answer this question in {timeout} seconds:\n{question}", end='', flush=True)
    while True:
        read_ready, _, _ = select([stdin], list(), list(), timeout)
        if not read_ready:
            return None
        choice = read_ready[0].readline().strip()
        if choice:
            return choice
        else:
            print('Please give an explicit answer: ', end='', flush=True)
