from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\adaptive_vad.py')
s=p.read_text(encoding='utf-8')
needle='    def has_speech(self, audio: bytes) -> bool:\n'
insert='''    def is_speech_frame(self, frame: bytes) -> bool:\n        if len(frame) % 2 or not frame:\n            return False\n        samples = [sample[0] for sample in struct.iter_unpack("<h", frame)]\n        rms = math.sqrt(sum(value * value for value in samples) / len(samples))\n        threshold = max(\n            self._minimum,\n            self._noise_floor * self._ratio + self._margin,\n            self._noise_peak_floor + self._margin,\n        )\n        return rms >= threshold\n\n'''
if needle not in s: raise SystemExit('needle missing')
p.write_text(s.replace(needle, insert+needle,1),encoding='utf-8',newline='\n')
