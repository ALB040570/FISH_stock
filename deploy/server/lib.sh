# shellcheck shell=bash
# Общие функции скриптов deploy/server (подключается через «.»).

# Сервисы за шлюзом: /api/<имя>/health
FISH_SERVICES="users data-model data-admin algo-model algo-admin dashboards help"

# wait_ready <адрес шлюза> <число попыток по 5 с>: 0 — все сервисы отвечают
wait_ready() {
  local url="$1" tries="$2" s all
  for _ in $(seq 1 "$tries"); do
    all=1
    for s in $FISH_SERVICES; do
      curl -fsS -m 5 "$url/api/$s/health" >/dev/null 2>&1 || { all=0; break; }
    done
    if [ "$all" = 1 ]; then return 0; fi
    sleep 5
  done
  echo "Не отвечает: /api/$s/" >&2
  return 1
}
