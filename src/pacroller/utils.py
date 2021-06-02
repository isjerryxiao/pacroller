import subprocess
from threading import Thread
import logging
from typing import List, BinaryIO, Iterator, Union
from io import DEFAULT_BUFFER_SIZE
from time import mktime
from datetime import datetime
from signal import SIGINT, SIGTERM, Signals
from select import select
from sys import stdin
logger = logging.getLogger()

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
    def set_timeout(p: subprocess.Popen, timeout: int) -> None:
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.exception(f'{timeout=} expired for {p}, terminating')
            terminate(p)
        else:
            logger.debug('set_timeout exit')
    p = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
    logger.debug(f"running {command}")
    try:
        Thread(target=set_timeout, args=(p, timeout), daemon=True).start()
        line = ''
        output = ''
        while (r := p.stdout.read(1)) != '':
            output += r
            line += r
            if r == '\n':
                logger.debug('STDOUT: %s', line[:-1])
                line = ''
            elif r == ']':
                if line == ':: Proceed with installation? [Y/n]':
                    p.stdin.write('y\n')
                    p.stdin.flush()
                elif line.lower().endswith('[y/n]'):
                    if interactive:
                        choice = ask_interactive_question(line, info=output)
                        if choice is None:
                            terminate(p, signal=SIGINT)
                            raise UnknownQuestionError(line, output)
                        elif choice:
                            p.stdin.write('y\n')
                            p.stdin.flush()
                        else:
                            p.stdin.write('n\n')
                            p.stdin.flush()
                    else:
                        terminate(p, signal=SIGINT)
                        raise UnknownQuestionError(line, output)
    except KeyboardInterrupt:
        terminate(p, signal=SIGINT)
        raise
    except Exception:
        terminate(p)
        raise
    if (ret := p.wait()) != 0:
        raise subprocess.CalledProcessError(ret, command, output)
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

def ask_interactive_question(question: str = "", timeout: int = 60, info: str = "") -> Union[bool, None]:
    ''' on timeout, returns None '''
    print(f"Please answer this question in {timeout} seconds:\n{question}", end=' ', flush=True)
    while True:
        read_ready, _, _ = select([stdin], list(), list(), timeout)
        if not read_ready:
            return None
        choice = read_ready[0].readline().strip()
        if choice.lower().startswith('y'):
            return True
        elif choice.lower().startswith('n'):
            return False
        else:
            if info and choice.lower().startswith('i'):
                print(info)
            print(f"Please give an explicit answer [Y]es [N]o{' [I]nfo' if info else ''}", end=' ', flush=True)
