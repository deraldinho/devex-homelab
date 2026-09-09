from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\human_interaction.py')
s=p.read_text(encoding='utf-8')
s=s.replace('    def handle(self, text: str) -> str | None:\n        clean = str(text).strip()','    def handle(self, text: str, *, source: str = "human.voice") -> str | None:\n        if source not in {"human.voice", "human.cli"}:\n            raise ValueError("human interaction source invalida")\n        clean = str(text).strip()',1)
s=s.replace('stimulus_id=f"human-{fingerprint[:16]}", source="human.voice",','stimulus_id=f"human-{fingerprint[:16]}", source=source,',1)
p.write_text(s,encoding='utf-8',newline='\n')
