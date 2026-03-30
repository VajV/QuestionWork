"""Run testsprite frontend tests in batches of 5."""
import subprocess
import sys
import os
import glob

test_dir = os.path.join(os.path.dirname(__file__), "frontend", "testsprite_tests")
python = os.path.join(os.path.dirname(__file__), "backend", ".venv", "Scripts", "python.exe")

# Collect all .py test files (exclude __pycache__ and tmp/)
test_files = sorted(glob.glob(os.path.join(test_dir, "*.py")))

batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 5
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0

batch = test_files[start:start + batch_size]
results = []

for tf in batch:
    name = os.path.basename(tf).split("_")[0]
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")
    proc = subprocess.run([python, tf], capture_output=True, text=True, timeout=120)
    status = "PASS" if proc.returncode == 0 else "FAIL"
    results.append((status, name, proc.returncode))
    if proc.returncode != 0:
        print(f"  STDERR (last 15 lines):")
        for line in proc.stderr.strip().split("\n")[-15:]:
            print(f"    {line}")
        if proc.stdout.strip():
            print(f"  STDOUT (last 5 lines):")
            for line in proc.stdout.strip().split("\n")[-5:]:
                print(f"    {line}")
    print(f"  Result: {status}")

print(f"\n{'='*60}")
print(f"BATCH SUMMARY (tests {start+1}-{start+len(batch)} of {len(test_files)})")
print(f"{'='*60}")
passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")
for status, name, code in results:
    print(f"  {status} {name} (exit={code})")
print(f"\nTotal: {passed} passed, {failed} failed")
