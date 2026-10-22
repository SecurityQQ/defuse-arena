#!/usr/bin/env python3
"""Run a command with a wall-clock timeout, killing the whole process group."""
import os
import signal
import subprocess
import sys

if len(sys.argv) < 3:
    print("usage: run_with_timeout.py <seconds> <command> [args...]", file=sys.stderr)
    sys.exit(2)

timeout = float(sys.argv[1])
cmd = sys.argv[2:]

proc = subprocess.Popen(cmd, start_new_session=True)
try:
    sys.exit(proc.wait(timeout=timeout))
except subprocess.TimeoutExpired:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    sys.exit(124)
