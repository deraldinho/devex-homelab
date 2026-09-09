#!/usr/bin/env bash
set -eu
pkill -TERM -f -- 'llama-cli -m /home/deraldinho/pentium-agent/runtime/llama/models/Qwen3-0.6B-Q4_0.gguf' || true
sleep 1
echo --FLAGS--
"$HOME/pentium-agent/runtime/llama/build/bin/llama-cli" --help 2>&1 | grep -Ei 'interactive|conversation|single|simple|prompt|batch|chat' | head -n 100
