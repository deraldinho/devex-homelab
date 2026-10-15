import subprocess
import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_host_preflight import inspect_opencode_host

class HostPreflightTests(unittest.TestCase):
    def test_missing_binary_is_blocked(self):
        self.assertEqual(inspect_opencode_host("/missing/atlas-opencode").reason,"binary_missing")
    def test_successful_version_is_ready_even_without_avx2(self):
        with tempfile.TemporaryDirectory() as d:
            exe=Path(d)/"opencode";exe.touch()
            cpu=Path(d)/"cpuinfo";cpu.write_text("flags: sse2")
            result=inspect_opencode_host(str(exe),cpuinfo_path=str(cpu),
                runner=lambda *a,**kw:subprocess.CompletedProcess([],0,"2.0.29",""))
            self.assertEqual((result.state,result.version),("READY","2.0.29"))
    def test_old_cpu_failed_binary_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            exe=Path(d)/"opencode";exe.touch()
            cpu=Path(d)/"cpuinfo";cpu.write_text("flags : fpu sse2 ssse3")
            result=inspect_opencode_host(str(exe),cpuinfo_path=str(cpu),
                runner=lambda *a,**kw:subprocess.CompletedProcess([],1,"",""))
            self.assertEqual(result.reason,"cpu_no_avx2_binary_failed")
    def test_timeout_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            exe=Path(d)/"opencode";exe.touch()
            def timeout(*args,**kwargs):raise subprocess.TimeoutExpired("opencode",8)
            self.assertEqual(inspect_opencode_host(str(exe),runner=timeout).reason,
                             "version_timeout")

if __name__=="__main__":unittest.main()
