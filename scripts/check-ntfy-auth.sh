#!/usr/bin/env bash
# Run this ON THE RASPBERRY PI (ssh in first) to see why ntfy is returning
# 403 Forbidden for anonymous publish/read on every topic.
set -euo pipefail

echo "=== ntfy server config (common locations) ==="
for f in /etc/ntfy/server.yml /etc/ntfy/server.yaml; do
    if [ -f "$f" ]; then
        echo "--- $f ---"
        grep -E 'auth-|behind-proxy|listen-' "$f" || echo "(no auth-related lines found)"
    fi
done

echo
echo "=== is ntfy running as a systemd service or docker container? ==="
systemctl status ntfy --no-pager 2>/dev/null | head -5 || true
docker ps --filter "name=ntfy" 2>/dev/null || true

echo
echo "=== existing ntfy users/tokens (if ntfy CLI is available) ==="
ntfy user list 2>&1 || echo "(ntfy CLI not found or no permission -- may need sudo)"
ntfy token list 2>&1 || true
