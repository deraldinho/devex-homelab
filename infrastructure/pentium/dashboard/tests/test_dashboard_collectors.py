import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard_collectors as dc
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoVisualAtlas
from infrastructure.pentium.atlas.visual_state_publisher import VisualStatePublisher


class CollectorTests(unittest.TestCase):
    def test_load_config_rejects_non_lan_bind(self):
        cfg = {"schema_version": 1, "bind_host": "0.0.0.0", "bind_port": 8765}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(ValueError):
                dc.load_config(path)

    def test_collect_status_always_has_stable_groups(self):
        cfg = dc.default_config()
        status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", "x"))
        self.assertEqual(set(status), {"atlas", "services", "voice", "audio", "anc", "system", "network", "visual", "cognition", "cognitive_runtime", "continuous_intent"})

    def test_parse_arecord_lists_internal_and_usb_capture_devices(self):
        text = """card 0: Intel [HDA Intel], device 0: ALC272 Analog [ALC272 Analog]\ncard 1: Device [USB Composite Device], device 0: USB Audio [USB Audio]\n"""
        devices = dc.parse_arecord_devices(text)
        self.assertEqual([d["card"] for d in devices], [0, 1])
        self.assertEqual(devices[1]["name"], "USB Audio")

    def test_sanitize_event_keeps_only_allowlisted_markers(self):
        allowed = dc.sanitize_event("Sep 07 atlas-voice ATLAS_V1_VOICE_DAEMON_LISTENING reason=no_speech")
        denied = dc.sanitize_event("Sep 07 atlas-voice user said secret phrase")
        self.assertIsNotNone(allowed)
        self.assertIsNone(denied)

    def test_collect_events_is_bounded(self):
        lines = "\n".join(["ATLAS_V1_VOICE_DAEMON_LISTENING reason=no_speech"] * 80)
        def runner(command, timeout):
            return dc.CommandResult(0, lines, "")
        events = dc.collect_events(dc.default_config(), command_runner=runner)
        self.assertLessEqual(len(events), 50)

    def test_parse_meminfo_reports_memory_and_swap_mb(self):
        text = "MemTotal: 2621440 kB\nMemAvailable: 524288 kB\nSwapTotal: 3145728 kB\nSwapFree: 2097152 kB\n"
        metrics = dc.parse_meminfo(text)
        self.assertEqual(metrics["memory_total_mb"], 2560)
        self.assertEqual(metrics["memory_available_mb"], 512)
        self.assertEqual(metrics["swap_used_mb"], 1024)

    def test_parse_ip_brief_extracts_ipv4_interfaces(self):
        text = "enp4s0 UP 192.168.88.3/24\nwlp1s0 UP 192.168.1.105/24 metric 600\ntailscale0 UNKNOWN 100.107.230.78/32\n"
        parsed = dc.parse_ip_brief(text)
        self.assertEqual(parsed["enp4s0"], "192.168.88.3/24")
        self.assertEqual(parsed["wlp1s0"], "192.168.1.105/24")
        self.assertEqual(parsed["tailscale0"], "100.107.230.78/32")

    def test_collect_status_reports_audio_and_network_inventory(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "health.json").write_text('{"status":"degraded"}', encoding="utf-8")
            (base / "voice.json").write_text('{"anc_enabled":false}', encoding="utf-8")
            (base / "sha").write_text("abc123\n", encoding="utf-8")
            cfg = dc.default_config() | {"health_path": str(base / "health.json"), "voice_config_path": str(base / "voice.json"), "deploy_sha_path": str(base / "sha")}
            def runner(command, timeout):
                if command[0] == "arecord":
                    return dc.CommandResult(0, "card 0: Intel [HDA Intel], device 0: ALC272 Analog [ALC272 Analog]\ncard 1: Device [USB Composite Device], device 0: USB Audio [USB Audio]\n", "")
                if command[0] == "ip":
                    return dc.CommandResult(0, "enp4s0 UP 192.168.88.3/24\nwlp1s0 UP 192.168.1.105/24\ntailscale0 UNKNOWN 100.107.230.78/32\n", "")
                return dc.CommandResult(0, "active\n", "")
            status = dc.collect_status(cfg, command_runner=runner)
        self.assertEqual(len(status["audio"]["devices"]), 2)
        self.assertEqual(status["network"]["lan"], "192.168.88.3/24")
        self.assertEqual(status["anc"]["state"], "off")

    def test_collect_status_checks_whisper_binary_without_reading_it(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            binary = base / "whisper-cli"
            binary.write_bytes(b"\xff\xfe\x00\x80")
            (base / "voice.json").write_text(json.dumps({"anc_enabled": False, "whisper_binary": str(binary)}), encoding="utf-8")
            (base / "health.json").write_text('{"status":"healthy"}', encoding="utf-8")
            (base / "sha").write_text("abc", encoding="utf-8")
            cfg = dc.default_config() | {"health_path": str(base / "health.json"), "voice_config_path": str(base / "voice.json"), "deploy_sha_path": str(base / "sha")}
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", ""))
        self.assertTrue(status["voice"]["whisper_available"])

    def test_collect_status_preserves_disabled_unit_state(self):
        cfg = dc.default_config()
        def runner(command, timeout):
            if command[:3] == ["systemctl", "--user", "is-enabled"]:
                return dc.CommandResult(1, "disabled\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                return dc.CommandResult(3, "inactive\n", "")
            return dc.CommandResult(1, "", "")
        status = dc.collect_status(cfg, command_runner=runner)
        self.assertEqual(status["services"]["voice"]["enabled"], "disabled")
        self.assertEqual(status["services"]["voice"]["active"], "inactive")

    def test_collect_status_uses_audio_system_and_network_sources(self):
        def runner(command, timeout):
            if command[:2] == ["arecord", "-l"]:
                return dc.CommandResult(0, "card 0: Intel [HDA Intel], device 0: ALC272 Analog [ALC272 Analog]\ncard 1: Device [USB Composite Device], device 0: USB Audio [USB Audio]\n", "")
            if command[:4] == ["ip", "-4", "-br", "addr"]:
                return dc.CommandResult(0, "enp4s0 UP 192.168.88.3/24\nwlp1s0 UP 192.168.1.105/24\ntailscale0 UNKNOWN 100.107.230.78/32\n", "")
            return dc.CommandResult(1, "", "unavailable")
        cfg = dc.default_config()
        status = dc.collect_status(cfg, command_runner=runner, meminfo_text="MemTotal: 2621440 kB\nMemAvailable: 524288 kB\nSwapTotal: 3145728 kB\nSwapFree: 2097152 kB\n", uptime_text="123.5 0.0")
        self.assertEqual(len(status["audio"]["devices"]), 2)
        self.assertEqual(status["system"]["memory_available_mb"], 512)
        self.assertEqual(status["system"]["uptime_s"], 123)
        self.assertEqual(status["network"]["lan"], "192.168.88.3/24")

    def test_collect_status_exposes_visual_snapshot_without_reclassifying_it(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            visual = {"versao_avatar": 1, "modo": "CONVERSANDO", "expressao": "ATENTO", "intensidade_expressao": 0.72, "foco_visual": "Deraldinho", "direcao_olhar": "frente", "gesto_atual": "nenhum", "velocidade_movimento": 0.4, "intensidade_movimento": 0.5, "falando": False, "ouvindo": True, "pensando": False, "duvida_identidade": False, "transicao_ms": 400}
            (base / "visual.json").write_text(json.dumps(visual), encoding="utf-8")
            cfg = dc.default_config() | {"visual_state_path": str(base / "visual.json")}
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", ""))
        self.assertEqual(status["visual"], visual)

    def test_collect_status_consumes_published_estado_visual_without_reclassification(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "visual-state.json"
            estado = EstadoVisualAtlas(
                modo="CONVERSANDO", expressao="CURIOSO", intensidade_expressao=0.63,
                foco_visual="core", direcao_olhar="core", gesto_atual="escuta",
                velocidade_movimento=0.47, intensidade_movimento=0.51,
                falando=False, ouvindo=True, pensando=False, duvida_identidade=False,
                transicao_ms=400,
            )
            VisualStatePublisher(path).publicar(estado)
            cfg = dc.default_config() | {"visual_state_path": str(path)}
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", ""))
        self.assertEqual(estado.para_dict(), status["visual"])

    def test_collect_status_falls_back_to_neutral_visual_state(self):
        cfg = dc.default_config() | {"visual_state_path": "Z:/missing/visual.json"}
        status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", ""))
        self.assertEqual(status["visual"]["modo"], "OCIOSO")
        self.assertEqual(status["visual"]["expressao"], "SERENO")
        self.assertEqual(status["visual"]["source"], "fallback")


class DashboardRuntimeTruthTests(unittest.TestCase):
    def test_collect_status_exposes_observation_service(self):
        cfg = dc.default_config()

        def runner(command, timeout):
            if command[:3] == ["systemctl", "--user", "is-enabled"]:
                return dc.CommandResult(0, "enabled\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                return dc.CommandResult(0, "active\n", "")
            return dc.CommandResult(1, "", "")

        status = dc.collect_status(cfg, command_runner=runner)
        self.assertEqual(status["services"]["observation"]["enabled"], "enabled")
        self.assertEqual(status["services"]["observation"]["active"], "active")
