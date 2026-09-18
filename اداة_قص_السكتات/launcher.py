import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")


def main():
    print("==============================================")
    print("  Silence Cut Tool - getting ready, please wait...")
    print("==============================================")

    if not os.path.exists(VENV_PYTHON):
        print("Setting up the environment for the first time...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)

    print("Installing required libraries (only happens once)...")
    subprocess.run(
        [VENV_PYTHON, "-m", "pip", "install", "-r",
         os.path.join(BASE_DIR, "requirements.txt"), "--quiet"],
        check=True,
    )

    print()
    print("==============================================")
    print("  Opening the Silence Cut Tool...")
    print("==============================================")
    print()

    subprocess.run([VENV_PYTHON, os.path.join(BASE_DIR, "cut_silence.py")])


if __name__ == "__main__":
    main()
