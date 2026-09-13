import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
EXPECTED_SHA = "a" * 40


class VoiceActivationSafeTests(unittest.TestCase):
    def _preflight_cls(self):
        try:
            from infrastructure.pentium.atlas.voice_activation_preflight import VoiceActivationPreflight
        except ModuleNotFoundError:
            self.fail("voice_activation_preflight_missing")
        return VoiceActivationPreflight

    def _ready_tree(self, root: Path):
        (root / "atlas" / "runtime").mkdir(parents=True)
        (root / "atlas" / "runtime" / "deployed-sha").write_text(EXPECTED_SHA + "\n", encoding="utf-8")
        for rel in (
            "runtime/whisper/build/bin/whisper-cli",
            "runtime/espeak-root/usr/bin/espeak-ng",
            "runtime/alsa-root/usr/bin/arecord",
            "runtime/alsa-root/usr/bin/aplay",
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("tool", encoding="utf-8")
            path.chmod(0o700)
        device_root = root / "dev" / "snd"
        device_root.mkdir(parents=True)
        for name in ("controlC0", "pcmC0D0c", "pcmC0D0p"):
            path = device_root / name
            path.write_text("device", encoding="utf-8")
            path.chmod(0o600)
        return device_root

    def test_voice_service_carries_identity_and_resource_bounds(self):
        service = (ATLAS / "atlas-voice.service").read_text(encoding="utf-8")
        for token in (
            "EnvironmentFile=-%h/pentium-agent/atlas/runtime/observation.env",
            "Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin",
            "UMask=0077", "MemoryHigh=256M", "MemoryMax=384M",
        ):
            self.assertIn(token, service)

    def test_preflight_reports_ready_only_with_audio_access_and_exact_sha(self):
        cls = self._preflight_cls()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            devices = self._ready_tree(root)
            result = cls(root, device_root=devices).run(EXPECTED_SHA, groups={"audio"})
            self.assertTrue(result["ready"])
            self.assertTrue(all(result["checks"].values()))
    def test_preflight_fails_closed_without_audio_group(self):
        cls = self._preflight_cls()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            devices = self._ready_tree(root)
            result = cls(root, device_root=devices).run(EXPECTED_SHA, groups=set())
            self.assertFalse(result["ready"])
            self.assertFalse(result["checks"]["audio_group"])

    def test_installer_packages_preflight(self):
        installer = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("voice_activation_preflight.py", installer)


if __name__ == "__main__":
    unittest.main()
