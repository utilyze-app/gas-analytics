
# Usage:
#   python run_scenarios.py
# This will call generator.py with scenarios.csv you can edit.

import subprocess, sys

def run():
    cmd = [sys.executable, "generator.py", "--config", "scenarios.csv"]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)

if __name__ == "__main__":
    run()
