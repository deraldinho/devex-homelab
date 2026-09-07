import unittest
from unittest.mock import patch

from infrastructure.pentium.atlas import voice_daemon


class AncWiringTests(unittest.TestCase):
    def test_disabled_anc_keeps_mono_capture(self):
        cfg = {'capture_device':'plughw:0,0','vad_frame_ms':20,'anc_enabled':False}
        sentinel = object()
        with patch.object(voice_daemon, 'open_arecord_pcm', return_value=sentinel) as opener:
            source = voice_daemon.build_audio_source('/bin/arecord', cfg)
        self.assertIs(sentinel, source)
        self.assertEqual(1, opener.call_args.kwargs['channels'])

    def test_enabled_anc_uses_stereo_and_wraps_nlms(self):
        cfg = {'capture_device':'plughw:0,0','vad_frame_ms':20,'anc_enabled':True,
               'anc_primary_channel':'left','anc_reference_channel':'right',
               'anc_taps':16,'anc_mu':0.3,'anc_calibration_frames':50}
        raw = object()
        with patch.object(voice_daemon, 'open_arecord_pcm', return_value=raw) as opener:
            with patch.object(voice_daemon, 'AdaptiveNoiseCancelledFrameSource', return_value='wrapped') as wrapper:
                source = voice_daemon.build_audio_source('/bin/arecord', cfg)
        self.assertEqual('wrapped', source)
        self.assertEqual(2, opener.call_args.kwargs['channels'])
        wrapper.assert_called_once()

class AncPackagingTests(unittest.TestCase):
    def test_config_defaults_off_and_installer_packages_anc(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / 'config_voice.json').read_text(encoding='utf-8'))
        self.assertFalse(cfg['anc_enabled'])
        self.assertEqual('left', cfg['anc_primary_channel'])
        self.assertEqual('right', cfg['anc_reference_channel'])
        install = (root / 'install-user.sh').read_text(encoding='utf-8')
        self.assertGreaterEqual(install.count('adaptive_noise_canceller.py'), 2)
