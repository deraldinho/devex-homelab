#!/usr/bin/env bash
set -euo pipefail
root="$HOME/pentium-agent/runtime/llama"
mkdir -p "$root/src" "$root/build" "$root/models"
if [[ ! -f "$root/src/CMakeLists.txt" ]]; then
  curl -L --fail https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.4.0.tar.gz -o /tmp/llama-v0.4.0.tar.gz
  tar -xzf /tmp/llama-v0.4.0.tar.gz --strip-components=1 -C "$root/src"
fi
cmake_bin="$HOME/pentium-agent/runtime/build/venv/bin/cmake"
"$cmake_bin" -S "$root/src" -B "$root/build" -DGGML_NATIVE=ON -DGGML_CCACHE=OFF -DLLAMA_CURL=OFF
"$cmake_bin" --build "$root/build" -j1 --target llama-cli
"$root/build/bin/llama-cli" --version
model="$root/models/Qwen3-0.6B-Q4_0.gguf"
if [[ ! -f "$model" ]]; then
  curl -L --fail https://huggingface.co/ggml-org/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_0.gguf -o "$model"
fi
echo 'da2572f16c06133561ce56accaa822216f2391ef4d37fba427801cd6736417d4  '"$model" | sha256sum -c -
ls -lh "$root/build/bin/llama-cli" "$model"
