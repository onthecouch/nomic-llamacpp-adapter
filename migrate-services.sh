#!/usr/bin/env bash
set -Eeuo pipefail

LLAMA_UNIT=/etc/systemd/system/llama-embedding.service
LLAMA_BACKUP=/etc/systemd/system/llama-embedding.service.pre-adapter
ADAPTER_UNIT=nomic-prefix-adapter.service

if [[ -r /etc/default/nomic-prefix-adapter ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/default/nomic-prefix-adapter
  set +a
fi
ADAPTER_HEALTH_URL="${ADAPTER_HEALTH_URL:-http://${ADAPTER_BIND_HOST:-127.0.0.1}:${ADAPTER_BIND_PORT:-8081}/health}"

rollback() {
  local status=$?
  trap - ERR
  systemctl disable --now "$ADAPTER_UNIT" >/dev/null 2>&1 || true
  if [[ -f "$LLAMA_BACKUP" ]]; then
    cp -a "$LLAMA_BACKUP" "$LLAMA_UNIT"
    systemctl daemon-reload
    systemctl restart llama-embedding.service
  fi
  exit "$status"
}
trap rollback ERR

cp -a "$LLAMA_UNIT" "$LLAMA_BACKUP"
cp /tmp/llama-embedding.service "$LLAMA_UNIT"
chmod 0644 "$LLAMA_UNIT" /etc/systemd/system/nomic-prefix-adapter.service
systemctl daemon-reload
systemctl restart llama-embedding.service

for _ in {1..30}; do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8082/health >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent --max-time 5 http://127.0.0.1:8082/health >/dev/null

systemctl enable --now "$ADAPTER_UNIT"
for _ in {1..15}; do
  if curl --fail --silent --max-time 2 "$ADAPTER_HEALTH_URL" >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent --max-time 5 "$ADAPTER_HEALTH_URL" >/dev/null

trap - ERR
