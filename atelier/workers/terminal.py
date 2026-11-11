"""PTY bridge. JSON-lines on stdio; the shell runs inside ConPTY/Unix PTY."""
import json
import os
import sys
import threading
from pathlib import Path
import re


def main():
    lock = threading.Lock()

    def send(**message):
        with lock:
            sys.stdout.buffer.write((json.dumps(message, ensure_ascii=True) + '\n').encode('utf-8'))
            sys.stdout.buffer.flush()
    root = sys.argv[1]
    env = os.environ.copy()
    env['TERM'] = 'xterm-256color'
    env['PYTHONIOENCODING'] = 'utf-8'
    input_id = 0
    prompt = re.compile(r'(?:^|[\r\n]|\x1b\[[0-9;?]*[A-Za-z])\[Atelier\] [A-Za-z]:[^>\r\n\x1b]*>')
    if len(sys.argv) > 2 and sys.argv[2]:
        interpreter = Path(sys.argv[2]).absolute()
        for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_PREFIX'):
            env.pop(key, None)
        env['PATH'] = str(interpreter.parent) + os.pathsep + env.get('PATH', '')
        environment = interpreter.parent.parent
        if (environment / 'pyvenv.cfg').exists():
            env['VIRTUAL_ENV'] = str(environment)
    if os.name == 'nt':
        from winpty import PtyProcess
        shell = os.environ.get('COMSPEC', 'cmd.exe')
        env['PROMPT'] = '[Atelier] $P$G'
        process = PtyProcess.spawn([shell, '/Q'], cwd=root, env=env, dimensions=(30, 110))
    else:
        from ptyprocess import PtyProcessUnicode
        process = PtyProcessUnicode.spawn(
            [os.environ.get('SHELL', '/bin/sh'), '-i'], cwd=root, env=env, dimensions=(30, 110))

    def reader():
        tail = ''
        try:
            # isalive() can briefly be false while ConPTY is starting.
            while True:
                text = process.read(8192)
                if text:
                    previous = len(tail)
                    tail += text
                    send(data=text)
                    if os.name == 'nt' and any(match.end() > previous for match in prompt.finditer(tail)):
                        send(prompt=input_id)
                    tail = tail[-1024:]
        except (EOFError, OSError):
            pass
        finally:
            try:
                send(exited=True)
            except (BrokenPipeError, OSError):
                pass
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    send(ready=True)
    try:
        for line in sys.stdin.buffer:
            try:
                message = json.loads(line)
                if 'input' in message:
                    input_id = message.get('id', input_id)
                    process.write(message['input'])
                elif 'resize' in message:
                    rows, columns = message['resize']
                    process.setwinsize(rows, columns)
                elif message.get('close'):
                    break
            except (ValueError, OSError, EOFError):
                pass
    finally:
        try:
            process.terminate(force=True)
        except (OSError, TypeError):
            try:
                process.close(force=True)
            except Exception:
                pass


def run():
    try:
        main()
    except Exception as error:
        print(json.dumps({'error': str(error)}), flush=True)
        sys.exit(1)


if __name__ == '__main__':
    run()
