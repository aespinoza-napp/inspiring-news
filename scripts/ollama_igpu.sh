#!/usr/bin/env bash
#
# Serve the dev machine's models from its integrated GPU (Vulkan) rather
# than its CPU. Measured 2026-10-21 on the Core Ultra 7 165U (Intel Arc,
# "Intel Graphics (MTL)"), one verifier call of 1,421 prompt tokens:
#
#                         prompt read      answer       call
#   CPU, Ollama default   ~45 tok/s        ~6 tok/s     ~64 s
#   CPU, 10 threads       ~62 tok/s        ~13 tok/s    ~33 s
#   integrated GPU        ~150 tok/s       ~9 tok/s     ~22 s
#
# docs/decisions/performance.md. The iGPU also gets Ollama's 32k default
# context instead of the CPU's 4k, so a writer's long prompt is no longer
# cut silently (docs/decisions/writing.md, "The model").
#
#   ./scripts/ollama_igpu.sh status   what Ollama computes on now
#   ./scripts/ollama_igpu.sh on       enable it (asks for sudo; restarts Ollama)
#   ./scripts/ollama_igpu.sh off      back to the CPU
#
# Linux with Ollama as the systemd service its installer creates. The
# service user must be able to open /dev/dri/renderD128 (group `render`).
# Production has no GPU: this is the dev machine only.

set -euo pipefail

DROP_IN=/etc/systemd/system/ollama.service.d/igpu.conf

status() {
  journalctl -u ollama --since "-1h" --no-pager 2>/dev/null \
    | grep -o 'msg="inference compute".*' | tail -1 \
    || echo "no 'inference compute' line in Ollama's log for the last hour; restart it to see one"
  [ -f "$DROP_IN" ] && echo "drop-in: $DROP_IN" || echo "drop-in: none (CPU)"
}

case "${1:-status}" in
  status)
    status
    ;;
  on)
    id -nG ollama | grep -qw render || sudo usermod -aG render ollama
    sudo mkdir -p "$(dirname "$DROP_IN")"
    printf '[Service]\nEnvironment="OLLAMA_IGPU_ENABLE=1"\nEnvironment="OLLAMA_VULKAN=1"\n' \
      | sudo tee "$DROP_IN" >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    sleep 3
    status
    ;;
  off)
    sudo rm -f "$DROP_IN"
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    sleep 3
    status
    ;;
  *)
    echo "usage: $0 status|on|off" >&2
    exit 2
    ;;
esac
