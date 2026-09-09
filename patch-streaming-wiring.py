from pathlib import Path
import json
root=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas')
# config
p=root/'config_voice.json'; cfg=json.loads(p.read_text(encoding='utf-8'))
cfg.update({'utterance_pre_roll_ms':200,'utterance_trailing_silence_ms':800,'utterance_max_s':12,'utterance_listen_window_s':4,'utterance_start_speech_frames':3,'stream_vad_calibration_frames':50,'stream_vad_history_frames':200})
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
# daemon imports + required fields + capture wiring
p=root/'voice_daemon.py'; s=p.read_text(encoding='utf-8')
s=s.replace('from .alsa_capture import AlsaCaptureBackend\n','from .alsa_capture import AlsaCaptureBackend\nfrom .alsa_stream import open_arecord_pcm\n')
s=s.replace('from .transcript_filter import NonSpeechTranscriptFilter\n','from .transcript_filter import NonSpeechTranscriptFilter\nfrom .streaming_vad import StreamingAdaptiveVad\nfrom .utterance_capture import StreamingUtteranceCapture\n')
s=s.replace('        "vad_frame_ms", "vad_min_speech_frames", "whisper_model", "whisper_timeout_s", "llm_model", "llm_timeout_s",','        "vad_frame_ms", "vad_min_speech_frames", "utterance_pre_roll_ms", "utterance_trailing_silence_ms",\n        "utterance_max_s", "utterance_listen_window_s", "utterance_start_speech_frames",\n        "stream_vad_calibration_frames", "stream_vad_history_frames",\n        "whisper_model", "whisper_timeout_s", "llm_model", "llm_timeout_s",')
old='''    capture = AlsaCaptureBackend(str(alsa / "usr/bin/arecord"), device=cfg["capture_device"], duration_s=int(cfg["capture_duration_s"]))\n    vad = AdaptiveEnergyVad(\n        min_rms_threshold=int(cfg["vad_rms_threshold"]), snr_ratio=float(cfg["vad_snr_ratio"]),\n        margin=int(cfg["vad_margin"]), calibration_frames=int(cfg["vad_calibration_frames"]),\n        alpha=float(cfg["vad_alpha"]), frame_ms=int(cfg["vad_frame_ms"]),\n        min_speech_frames=int(cfg["vad_min_speech_frames"]),\n        max_samples=int(cfg["capture_duration_s"]) * 16000,\n    )\n'''
new='''    stream_vad = StreamingAdaptiveVad(\n        calibration_frames=int(cfg["stream_vad_calibration_frames"]),\n        history_frames=int(cfg["stream_vad_history_frames"]),\n        min_rms_threshold=int(cfg["vad_rms_threshold"]), snr_ratio=float(cfg["vad_snr_ratio"]),\n        margin=int(cfg["vad_margin"]),\n    )\n    capture = StreamingUtteranceCapture(\n        lambda: open_arecord_pcm(str(alsa / "usr/bin/arecord"), device=cfg["capture_device"], frame_ms=int(cfg["vad_frame_ms"])),\n        stream_vad, frame_ms=int(cfg["vad_frame_ms"]),\n        start_speech_frames=int(cfg["utterance_start_speech_frames"]),\n        trailing_silence_ms=int(cfg["utterance_trailing_silence_ms"]),\n        max_utterance_s=int(cfg["utterance_max_s"]), pre_roll_ms=int(cfg["utterance_pre_roll_ms"]),\n        listen_window_s=int(cfg["utterance_listen_window_s"]),\n    )\n'''
if old not in s: raise SystemExit('capture block not found')
s=s.replace(old,new,1)
s=s.replace('return VoiceRuntime(capture, stt, gate, interaction, tts, vad=vad, transcript_filter=transcript_filter)','return VoiceRuntime(capture, stt, gate, interaction, tts, transcript_filter=transcript_filter)')
p.write_text(s,encoding='utf-8',newline='\n')
# installer copy + compile
p=root/'install-user.sh'; s=p.read_text(encoding='utf-8')
s=s.replace('  alsa_capture.py \\\n  whisper_stt.py \\','  alsa_capture.py \\\n  alsa_stream.py \\\n  utterance_capture.py \\\n  streaming_vad.py \\\n  whisper_stt.py \\',1)
s=s.replace('  "${TARGET_DIR}/alsa_capture.py" \\\n  "${TARGET_DIR}/whisper_stt.py" \\','  "${TARGET_DIR}/alsa_capture.py" \\\n  "${TARGET_DIR}/alsa_stream.py" \\\n  "${TARGET_DIR}/utterance_capture.py" \\\n  "${TARGET_DIR}/streaming_vad.py" \\\n  "${TARGET_DIR}/whisper_stt.py" \\',1)
p.write_text(s,encoding='utf-8',newline='\n')
