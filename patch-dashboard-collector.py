from pathlib import Path
p = Path(r"C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-dashboard\infrastructure\pentium\dashboard\dashboard_collectors.py")
s = p.read_text(encoding="utf-8")
old = '''        system.update(parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8")))
        system["uptime_s"] = round(float(Path("/proc/uptime").read_text().split()[0]), 1)
'''
new = '''        system.update(parse_meminfo(meminfo_text if meminfo_text is not None else Path("/proc/meminfo").read_text(encoding="utf-8")))
        uptime_raw = uptime_text if uptime_text is not None else Path("/proc/uptime").read_text(encoding="utf-8")
        system["uptime_s"] = int(float(uptime_raw.split()[0]))
'''
if old not in s:
    raise SystemExit("target block not found")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
