#!/usr/bin/env bash
# Открыть FishStock снаружи через системный nginx сервера, с HTTPS (Let's Encrypt).
# Добавляет ОДИН файл /etc/nginx/sites-available/fishstock (+ ссылку в sites-enabled); другие сайты не трогает.
# Перед перезагрузкой nginx проверяет конфигурацию; при ошибке убирает свой файл и nginx не перезагружает.
#
#   ~/fishstock/deploy/server/nginx_site.sh [домен]
#
# Домен по умолчанию — fishstock.<IP-через-дефисы>.sslip.io (указывает на этот сервер, DNS не нужен).
# Порт приложения берётся из .env (FISH_HTTP_PORT). Нужен пароль sudo.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"
[ -f .env ] || { echo "Сначала выполните deploy/server/install.sh"; exit 1; }
# shellcheck disable=SC1091
set -a; . ./.env; set +a
UPSTREAM="${FISH_HTTP_PORT}"
case "$UPSTREAM" in *:*) ;; *) UPSTREAM="127.0.0.1:${UPSTREAM}" ;; esac

IP="$(curl -fsS https://api.ipify.org || true)"
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  [ -n "$IP" ] || { echo "Не удалось узнать внешний IP; укажите домен: $0 fishstock.example.kz"; exit 1; }
  DOMAIN="fishstock.${IP//./-}.sslip.io"
fi
SITE=/etc/nginx/sites-available/fishstock
LINK=/etc/nginx/sites-enabled/fishstock

echo "== Домен: $DOMAIN  ->  http://$UPSTREAM"
curl -fsS "http://$UPSTREAM/api/users/health" >/dev/null || { echo "Приложение не отвечает на $UPSTREAM — запустите install.sh"; exit 1; }
command -v nginx >/dev/null || { echo "Системный nginx не найден"; exit 1; }

sudo -v
if [ -f "$SITE" ]; then sudo cp "$SITE" "$SITE.bak.$(date +%Y%m%d%H%M%S)"; fi

TMP="$(mktemp)"
cat > "$TMP" <<EOF
# FishStock (временный сервер). Создано $DIR/deploy/server/nginx_site.sh $(date '+%Y-%m-%d %H:%M').
# Приложение — Docker Compose в $DIR, слушает только $UPSTREAM.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 100m;

    location / {
        proxy_pass http://$UPSTREAM;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
sudo install -m 644 "$TMP" "$SITE"
rm -f "$TMP"
sudo ln -sfn "$SITE" "$LINK"

echo "== Проверка конфигурации nginx"
if ! sudo nginx -t; then
  echo "Конфигурация с ошибкой — убираю файл FishStock, nginx НЕ перезагружается"
  sudo rm -f "$LINK" "$SITE"
  exit 1
fi
sudo systemctl reload nginx
echo "HTTP работает: http://$DOMAIN"

echo "== Сертификат HTTPS (Let's Encrypt)"
if ! command -v certbot >/dev/null; then
  echo "certbot не установлен — устанавливаю (apt)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq certbot python3-certbot-nginx
fi
if sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect; then
  sudo nginx -t && sudo systemctl reload nginx
  echo
  echo "Готово: https://$DOMAIN"
else
  echo
  echo "Сертификат выпустить не удалось (проверьте, что порт 80 открыт из интернета)."
  echo "Приложение доступно без шифрования: http://$DOMAIN"
  exit 1
fi
