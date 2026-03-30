"""
Local E2E test runner — runs the same Playwright tests that TestSprite generates,
but directly on the local machine (no tunnel, no cloud).

Usage:
    python scripts/run_e2e_tests.py                   # run all tests
    python scripts/run_e2e_tests.py auth-login        # run tests matching pattern
    python scripts/run_e2e_tests.py --list            # list available tests
    python scripts/run_e2e_tests.py --workers 3       # run 3 tests at a time (default: 3)

Requirements:
    pip install playwright
    python -m playwright install chromium

Servers must be running:
    Backend:  http://127.0.0.1:8001
    Frontend: http://127.0.0.1:3001
"""

import asyncio
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

TESTS_DIR = Path(__file__).parent.parent.parent / "frontend" / "testsprite_tests"
# Use sys.executable so that whatever Python is running this script also runs the tests.
# This avoids hard-coding .venv paths that may be blocked by workspace hooks.
PYTHON_EXE = sys.executable

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def find_test_files(pattern: Optional[str] = None) -> list[Path]:
    files = sorted(TESTS_DIR.glob("*.py"))
    if pattern:
        files = [f for f in files if pattern.lower() in f.name.lower()]
    return files


def extract_test_name(path: Path) -> str:
    name = path.stem  # e.g. auth-login-success_User_can_log_in_with_valid_credentials
    return name.split("_")[0]  # e.g. auth-login-success


async def run_single_test(test_file: Path) -> dict:
    """Execute a single test file and return result dict."""
    test_name = extract_test_name(test_file)
    code = test_file.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM if present

    # Patch 1: remove --single-process (crashes Chromium on Windows/non-container)
    code = code.replace('"--single-process"', '# "--single-process" removed for local run')
    code = code.replace("'--single-process'", "# '--single-process' removed for local run")

    # Patch 2: raise default_timeout from 5s to 15s
    code = code.replace("context.set_default_timeout(5000)", "context.set_default_timeout(15000)")

    # Patch 3+4: Replace the entire args=[...] block in chromium.launch() with
    # safe local testing args. Removes --single-process and adds --disable-web-security
    # (standard for headless Playwright tests against localhost — bypasses CORS).
    import re as _re
    _safe_args = (
        'args=[\n'
        '                "--window-size=1280,720",\n'
        '                "--disable-dev-shm-usage",\n'
        '                "--ipc=host",\n'
        '                "--disable-web-security",\n'
        '                "--disable-features=IsolateOrigins,site-per-process",\n'
        '            ],'
    )
    code = _re.sub(r'args=\[.*?\],', _safe_args, code, flags=_re.DOTALL)

    # Patch 5: normalize URL — TestSprite may hardcode localhost:3000 or :3001
    code = code.replace("http://localhost:3000", "http://127.0.0.1:3001")
    code = code.replace("http://localhost:3001", "http://127.0.0.1:3001")

    start = time.time()
    result = {
        "name": test_name,
        "file": test_file.name,
        "status": "PASSED",
        "error": None,
        "duration": 0.0,
    }

    # Execute in a subprocess so crashes don't kill the whole runner
    proc = await asyncio.create_subprocess_exec(
        PYTHON_EXE,
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(TESTS_DIR),
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
    except asyncio.TimeoutError:
        proc.kill()
        result["status"] = "TIMEOUT"
        result["error"] = "Test timed out after 90 seconds"
    else:
        result["duration"] = round(time.time() - start, 1)
        if proc.returncode != 0:
            result["status"] = "FAILED"
            err_text = stderr.decode("utf-8", errors="replace").strip()
            result["error"] = err_text[-800:] if len(err_text) > 800 else err_text

    result["duration"] = round(time.time() - start, 1)
    return result


def print_result(r: dict) -> None:
    status = r["status"]
    if status == "PASSED":
        icon = f"{GREEN}✓{RESET}"
        color = GREEN
    elif status == "TIMEOUT":
        icon = f"{YELLOW}⏱{RESET}"
        color = YELLOW
    else:
        icon = f"{RED}✗{RESET}"
        color = RED

    print(f"  {icon} {color}{r['name']}{RESET}  ({r['duration']}s)")
    if r["error"]:
        for line in r["error"].splitlines()[-6:]:
            print(f"       {YELLOW}{line}{RESET}")


async def run_all(pattern: Optional[str], max_workers: int) -> None:
    files = find_test_files(pattern)
    if not files:
        print(f"{RED}No test files found{'' if not pattern else f' matching: {pattern}'}{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}{CYAN}QuestionWork E2E — Local Playwright Runner{RESET}")
    print(f"Tests dir : {TESTS_DIR}")
    print(f"Running   : {len(files)} tests (max {max_workers} parallel)\n")

    semaphore = asyncio.Semaphore(max_workers)
    results = []

    async def bounded(f):
        async with semaphore:
            r = await run_single_test(f)
            print_result(r)
            return r

    tasks = [bounded(f) for f in files]
    results = await asyncio.gather(*tasks)

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    timeout = sum(1 for r in results if r["status"] == "TIMEOUT")
    total = len(results)

    print(f"\n{'─' * 50}")
    print(f"{BOLD}Results: {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  {YELLOW}{timeout} timeout{RESET}  / {total} total{RESET}")

    if failed or timeout:
        print(f"\n{RED}Failed tests:{RESET}")
        for r in results:
            if r["status"] != "PASSED":
                print(f"  • {r['name']} [{r['status']}]")
                if r["error"]:
                    for line in r["error"].splitlines()[-3:]:
                        print(f"      {line}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}{BOLD}All tests passed! 🎉{RESET}")


def main():
    args = sys.argv[1:]
    pattern = None
    max_workers = 3

    if "--list" in args:
        files = find_test_files()
        print(f"\nAvailable tests in {TESTS_DIR}:\n")
        for f in files:
            print(f"  {extract_test_name(f)}")
        print(f"\nTotal: {len(files)} tests")
        return

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--workers" and i + 1 < len(args):
            max_workers = int(args[i + 1])
            i += 2
        elif not arg.startswith("--"):
            pattern = arg
            i += 1
        else:
            i += 1

    asyncio.run(run_all(pattern, max_workers))


if __name__ == "__main__":
    main()
