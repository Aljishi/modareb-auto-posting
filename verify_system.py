#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Verification Tool for Rased Project
Checks: File existence, imports, data flow, and workflow configuration
"""

import os
import sys
import json
import yaml
from pathlib import Path

class SystemVerifier:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.scripts_dir = self.base_dir / "scripts"
        self.data_dir = self.base_dir / "data"
        self.workflow_file = self.base_dir / ".github" / "workflows" / "post.yml"
        
        self.required_files = {
            # Core workflow
            '.github/workflows/post.yml': 'Main workflow with 4 jobs',
            
            # Market data jobs
            'scripts/is_market_open.py': 'Check Saudi market hours',
            'scripts/market_intelligence.py': 'Fetch data from multiple sources',
            'scripts/fetch_api_data.py': 'Fallback data fetcher',
            
            # Signal generation
            'scripts/generate_signal.py': 'Generate trading signals',
            'scripts/should_post.py': 'Validate signal conditions',
            
            # Posting jobs
            'scripts/generate_post.py': 'Create post image',
            'scripts/post_to_telegram.py': 'Post to Telegram',
            'scripts/post_to_facebook.py': 'Post to Facebook (optional)',
            'scripts/post_to_instagram.py': 'Post to Instagram (optional)',
            
            # Golden signal job
            'scripts/golden_signal_analysis.py': 'Deep analysis for golden signals',
            'scripts/check_golden_signal.py': 'Check if golden signals exist',
            'scripts/generate_golden_post.py': 'Create golden post image',
            'scripts/post_golden_signal.py': 'Post golden signal to Telegram',
            
            # Weekly report job
            'scripts/weekly_report.py': 'Generate weekly report',
            'scripts/post_weekly_report.py': 'Post weekly report to Telegram',
            
            # Track results job
            'scripts/track_results.py': 'Track signal performance',
            'scripts/update_track_record.py': 'Update GitHub Pages track record',
            
            # Config & dependencies
            'requirements.txt': 'Python dependencies',
            'config.py': 'Configuration settings (optional)',
        }
        
        self.required_data_files = [
            'data/daily.json',
            'data/signals.json', 
            'data/validated_signals.json',
            'data/golden_signals.json',
            'data/track_record.json',
            'data/weekly_report.json',
        ]
        
        self.errors = []
        self.warnings = []
        self.successes = []

    def check_file_exists(self, filepath, description):
        """Check if a file exists"""
        full_path = self.base_dir / filepath if not filepath.startswith('scripts/') and not filepath.startswith('.github/') else self.base_dir / filepath
        if full_path.exists():
            self.successes.append(f"✅ {filepath}: {description}")
            return True
        else:
            self.errors.append(f"❌ MISSING: {filepath} - {description}")
            return False

    def check_python_syntax(self, filepath):
        """Check if Python file has valid syntax"""
        import py_compile
        try:
            py_compile.compile(filepath, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            self.errors.append(f"❌ SYNTAX ERROR in {filepath}: {e}")
            return False

    def check_imports(self, filepath):
        """Check if imports in Python file are valid"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic check for common missing imports
            if 'requests' in content and 'import requests' not in content:
                self.warnings.append(f"⚠️ {filepath}: Uses 'requests' but may not import it")
            
            if 'pandas' in content and 'import pandas' not in content and 'import pd' not in content:
                self.warnings.append(f"⚠️ {filepath}: Uses 'pandas' but may not import it")
                
            return True
        except Exception as e:
            self.warnings.append(f"⚠️ Could not check imports in {filepath}: {e}")
            return True  # Don't fail on import check

    def check_workflow_structure(self):
        """Check if workflow has all 4 required jobs"""
        if not self.workflow_file.exists():
            self.errors.append("❌ Workflow file not found")
            return False
        
        try:
            with open(self.workflow_file, 'r', encoding='utf-8') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            required_jobs = ['auto-post', 'track-results', 'weekly-report', 'golden-signal']
            
            for job in required_jobs:
                if job in jobs:
                    self.successes.append(f"✅ Workflow job '{job}' exists")
                else:
                    self.errors.append(f"❌ MISSING WORKFLOW JOB: '{job}'")
            
            # Check cron schedules
            schedules = workflow.get('on', {}).get('schedule', [])
            if schedules:
                self.successes.append(f"✅ Workflow has {len(schedules)} scheduled triggers")
            else:
                self.warnings.append("⚠️ Workflow may not have scheduled triggers")
                
            return True
        except Exception as e:
            self.errors.append(f"❌ Could not parse workflow: {e}")
            return False

    def check_data_flow(self):
        """Check if data files are properly connected between scripts"""
        # Check generate_signal.py outputs to signals.json
        gen_signal = self.scripts_dir / "generate_signal.py"
        if gen_signal.exists():
            with open(gen_signal, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'signals.json' in content or 'validated_signals.json' in content:
                self.successes.append("✅ generate_signal.py outputs to signals file")
            else:
                self.warnings.append("⚠️ generate_signal.py may not output to expected file")
        
        # Check should_post.py reads from signals.json
        should_post = self.scripts_dir / "should_post.py"
        if should_post.exists():
            with open(should_post, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'signals.json' in content:
                self.successes.append("✅ should_post.py reads from signals file")
        
        # Check post_to_telegram.py reads from validated_signals.json or signals.json
        post_telegram = self.scripts_dir / "post_to_telegram.py"
        if post_telegram.exists():
            with open(post_telegram, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'validated_signals.json' in content or 'signals.json' in content:
                self.successes.append("✅ post_to_telegram.py reads from signals file")
        
        return True

    def check_requirements(self):
        """Check if requirements.txt has all needed packages"""
        req_file = self.base_dir / "requirements.txt"
        if not req_file.exists():
            self.errors.append("❌ requirements.txt not found")
            return False
        
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        required_packages = [
            'requests', 'pytz', 'pillow', 'pandas', 'numpy',
            'arabic-reshaper', 'python-bidi', 'beautifulsoup4'
        ]
        
        for pkg in required_packages:
            if pkg in content:
                self.successes.append(f"✅ Requirement: {pkg}")
            else:
                self.warnings.append(f"⚠️ Missing recommended package: {pkg}")
        
        return True

    def run_full_check(self):
        """Run all verification checks"""
        print("=" * 70)
        print("🔍 راصد - أداة التحقق من ترابط النظام")
        print("=" * 70)
        print(f"📁 المشروع: {self.base_dir}")
        print()
        
        # 1. Check all required files exist
        print("📋 Checking required files...")
        for filepath, description in self.required_files.items():
            self.check_file_exists(filepath, description)
        
        # 2. Check Python syntax for scripts
        print("\n🐍 Checking Python syntax...")
        for script in self.scripts_dir.glob("*.py"):
            self.check_python_syntax(script)
        
        # 3. Check imports
        print("\n📦 Checking imports...")
        for script in self.scripts_dir.glob("*.py"):
            self.check_imports(script)
        
        # 4. Check workflow structure
        print("\n⚙️ Checking workflow structure...")
        self.check_workflow_structure()
        
        # 5. Check data flow
        print("\n🔄 Checking data flow...")
        self.check_data_flow()
        
        # 6. Check requirements
        print("\n📦 Checking requirements.txt...")
        self.check_requirements()
        
        # Print results
        print("\n" + "=" * 70)
        print("📊 النتائج:")
        print("=" * 70)
        
        if self.successes:
            print(f"\n✅ النجاح ({len(self.successes)}):")
            for s in self.successes[:10]:  # Show first 10
                print(f"  {s}")
            if len(self.successes) > 10:
                print(f"  ... و {len(self.successes) - 10} أخرى")
        
        if self.warnings:
            print(f"\n⚠️ تحذيرات ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  {w}")
        
        if self.errors:
            print(f"\n❌ أخطاء ({len(self.errors)}):")
            for e in self.errors:
                print(f"  {e}")
            print(f"\n🔧 يرجى إصلاح {len(self.errors)} خطأ قبل التشغيل")
            return False
        else:
            print(f"\n🎉 النظام جاهز! جميع الملفات موجودة ومترابطة")
            return True

def main():
    verifier = SystemVerifier()
    success = verifier.run_full_check()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # Try to import yaml, if not available, skip workflow check
    try:
        import yaml
    except ImportError:
        print("⚠️ pyyaml not installed, skipping workflow YAML parsing")
        # Create a dummy yaml module to avoid errors
        import sys
        class DummyYAML:
            @staticmethod
            def safe_load(f):
                return {'jobs': {}, 'on': {}}
        sys.modules['yaml'] = DummyYAML()
    
    main()

