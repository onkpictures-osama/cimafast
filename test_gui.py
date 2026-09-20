#!/usr/bin/env python3
"""CimaFast Studio - Comprehensive Test Suite"""
import requests, os, sys

class CimaFastTester:
    def __init__(self, base_url="http://127.0.0.1:8501"):
        self.base_url = base_url
        self.results = []
    
    def log(self, status, name, details=""):
        icon = "✅" if status else "❌"
        self.results.append(status)
        print(f"{icon} {name}" + (f" → {details}" if details else ""))
    
    def test_app_running(self):
        try:
            r = requests.get(self.base_url, timeout=5)
            self.log(r.status_code in [200, 301, 302], "App Running", f"Status {r.status_code}")
        except: self.log(False, "App Running")
    
    def test_claude_signature(self):
        try:
            r = requests.get(self.base_url, timeout=5)
            has = "Claude" in r.text or "🤖" in r.text
            self.log(has, "Claude Signature", "Found" if has else "Missing")
        except: self.log(False, "Claude Signature")
    
    def test_job_titles(self):
        try:
            with open('/srv/cimafast/database.py', 'r', encoding='utf-8') as f:
                has = "VFX Supervisor" in f.read() or "مشرف المؤثرات" in f.read()
            self.log(has, "VFX Supervisor Role", "Found" if has else "Missing")
        except: self.log(False, "VFX Supervisor Role")
    
    def test_auth(self):
        try:
            from auth import hash_password, verify_password
            h = hash_password("test123")
            v = verify_password("test123", h)
            self.log(v, "Auth System", "Working" if v else "Failed")
        except: self.log(False, "Auth System")
    
    def test_git(self):
        try:
            import subprocess
            r = subprocess.run(['git', 'rev-parse', '--git-dir'], cwd='/srv/cimafast', capture_output=True)
            self.log(r.returncode == 0, "Git Repository", "Initialized" if r.returncode == 0 else "Missing")
        except: self.log(False, "Git Repository")
    
    def test_signup(self):
        try:
            with open('/srv/cimafast/app.py', 'r', encoding='utf-8') as f:
                has = "_render_signup_screen" in f.read()
            self.log(has, "Signup Module", "Integrated" if has else "Missing")
        except: self.log(False, "Signup Module")
    
    def test_backup(self):
        has = os.path.isdir('/srv/cimafast/backups')
        self.log(has, "Backup System", "Ready" if has else "Missing")
    
    def test_agents(self):
        try:
            agents = ['orchestrator.md', 'production.md', 'universal-creative.md', 'infrastructure.md']
            has = all(os.path.exists(f'/srv/cimafast/.claude/agents/{a}') for a in agents)
            self.log(has, "4-Agent Personas", "Deployed" if has else "Missing")
        except: self.log(False, "4-Agent Personas")
    
    def run(self):
        print("\n" + "="*60)
        print("🧪 CimaFast Studio - Test Suite")
        print("="*60 + "\n")
        self.test_app_running()
        self.test_claude_signature()
        self.test_job_titles()
        self.test_auth()
        self.test_git()
        self.test_signup()
        self.test_backup()
        self.test_agents()
        passed = sum(self.results)
        total = len(self.results)
        print("\n" + "="*60)
        print(f"📊 {passed}/{total} tests passed")
        print("="*60 + "\n")
        return passed == total

if __name__ == "__main__":
    success = CimaFastTester().run()
    exit(0 if success else 1)
