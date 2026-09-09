from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_v1_utterance_capture.py')
s=p.read_text(encoding='utf-8')
s=s.replace("        with wave.open(io.BytesIO(audio), 'rb') as wav:\n            self.assertEqual(0, wav.getnframes())\n        self.assertEqual(150, len(source.frames))", "        self.assertEqual(b'', audio)\n        self.assertEqual(150, len(source.frames))",1)
p.write_text(s,encoding='utf-8',newline='\n')
