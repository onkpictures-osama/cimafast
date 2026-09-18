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


def skip_streamlit_email_prompt():
    config_dir = os.path.join(os.path.expanduser("~"), ".streamlit")
    credentials_path = os.path.join(config_dir, "credentials.toml")
    if not os.path.exists(credentials_path):
        os.makedirs(config_dir, exist_ok=True)
        with open(credentials_path, "w", encoding="utf-8") as f:
            f.write("[general]\nemail = \"\"\n")


def main():
    # الرسائل هنا بالإنجليزي على قصد: شاشة الأوامر (cmd) القديمة بتاعة ويندوز
    # مش بتعرض العربي صح (بتقلب ترتيب الحروف)، فالإنجليزي هنا أوضح وأسلم.
    print("==============================================")
    print("  CimaFast Studio - getting ready, please wait...")
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

    skip_streamlit_email_prompt()

    print()
    print("==============================================")
    print("  Opening CimaFast Studio in your browser now...")
    print("==============================================")
    print()

    subprocess.run([VENV_PYTHON, "-m", "streamlit", "run", os.path.join(BASE_DIR, "app.py")])


if __name__ == "__main__":
    main()
