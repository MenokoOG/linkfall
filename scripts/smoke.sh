#!/usr/bin/env bash
# Smoke tests for the compose stack (ADR 0004). Run after `docker compose up -d`.
# Each check prints PASS or FAIL. Exit code is the number of failures.
set -uo pipefail

fails=0
check() { # name, command...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS  $name"; else echo "FAIL  $name"; fails=$((fails + 1)); fi
}
refuse() { # name, command...: passes when the command fails
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "FAIL  $name"; fails=$((fails + 1)); else echo "PASS  $name"; fi
}
api() { docker compose exec -T api "$@"; }
model() { docker compose exec -T model "$@"; }

check  "api answers on 127.0.0.1:8000"            curl -fsS --max-time 5 http://127.0.0.1:8000/api/health
check  "console is served"                        curl -fsS --max-time 5 http://127.0.0.1:8000/
check  "range page is served"                     curl -fsS --max-time 5 http://127.0.0.1:8000/range.html
check  "range lists its targets"                  bash -c "curl -fsS --max-time 5 http://127.0.0.1:8000/api/range | grep -q '\"reference\"'"
refuse "range start needs the request header"     curl -fsS --max-time 5 -X POST -H 'Content-Type: application/json' -d '{"target":"reference"}' http://127.0.0.1:8000/api/range/runs
refuse "api rejects a foreign Host header"        curl -fsS --max-time 5 -H 'Host: evil.example' http://127.0.0.1:8000/api/health
check  "api port is published on loopback only"   bash -c "docker compose port api 8000 | grep -q '^127.0.0.1:'"
check  "model publishes no port"                  bash -c "[[ \"\$(docker inspect \$(docker compose ps -q model) --format '{{json .NetworkSettings.Ports}}')\" == '{\"8090/tcp\":null}' ]]"
check  "api reaches the model over backend"       api python -c "import urllib.request as u; u.urlopen('http://model:8090/health', timeout=5)"
refuse "model has no route to the internet"       model bash -c "exec 3<>/dev/tcp/1.1.1.1/443"
refuse "model cannot resolve a public name"       model getent hosts example.com
check  "api runs as non-root"                     bash -c "[[ \"\$(docker compose exec -T api id -u)\" != 0 ]]"
check  "model runs as non-root"                   bash -c "[[ \"\$(docker compose exec -T model id -u)\" != 0 ]]"
refuse "api image has no .git metadata"       api sh -c "test -e /app/.git || find / -maxdepth 3 -name .git -not -path '/proc/*' | grep -q ."
refuse "api image has no virtualenv or bytecode cache copied in" api sh -c "find /app/src \\( -name .venv -o -name pyvenv.cfg -o -name __pycache__ \\) | grep -q ."
refuse "api root filesystem is read-only"         api touch /app/probe
check  "api can write its data volume"            api sh -c "touch /data/.probe && rm /data/.probe"
refuse "model mount is read-only"                 model touch /models/probe

echo "$fails failure(s)"
exit "$fails"
