import subprocess, sys, os
os.chdir(os.path.join(os.path.dirname(__file__)))
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
    capture_output=True, text=True, timeout=300
)
out = os.path.join(os.path.dirname(__file__), "test_output_full.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout or "(empty)")
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr or "(empty)")
    f.write(f"\n=== EXIT CODE: {result.returncode} ===\n")
# Print summary to stdout
lines = (result.stdout + result.stderr).strip().splitlines()
for line in lines[-10:]:
    print(line)
print(f"EXIT_CODE={result.returncode}")
