from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_llama_cpp_backend.py')
t = p.read_text(encoding='utf-8')
needle = '        self.assertIn("--single-turn", argv)\n        self.assertIn("--simple-io", argv)\n        self.assertEqual(["--reasoning", "off"], argv[argv.index("--reasoning"):argv.index("--reasoning") + 2])'
replacement = needle + '\n        self.assertIn("--log-disable", argv)\n        self.assertIn("--no-display-prompt", argv)'
if needle not in t:
    raise SystemExit('needle not found')
p.write_text(t.replace(needle, replacement, 1), encoding='utf-8')
