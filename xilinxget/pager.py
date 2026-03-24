import os
import shlex
import subprocess
import sys
from contextlib import contextmanager, redirect_stdout


def _pager_cmd():
    if os.name == "nt":
        # Windows: uses 'more' (limited ANSI)
        return shlex.split(os.environ.get("PAGER", "more"))
    else:
        # POSIX: -R keep colors, -F quit if one screen, -X no alt screen, -E quit at end
        return shlex.split(os.environ.get("PAGER", "less -R -F -X -E"))


@contextmanager
def system_pager(enabled=None):
    """Yield a writable stream connected to the system pager."""
    if enabled is None:
        enabled = sys.stdout.isatty()  # disable when piped to file
    if not enabled:
        yield sys.stdout
        return
    try:
        p = subprocess.Popen(_pager_cmd(), stdin=subprocess.PIPE, text=True)
    except FileNotFoundError:
        # fall back to normal stdout if pager not found
        yield sys.stdout
        return
    try:
        yield p.stdin
    finally:
        try:
            p.stdin.close()
        except Exception:
            pass
        p.wait()


def pager_print(text: str):
    with system_pager() as out, redirect_stdout(out):
        print(text)
