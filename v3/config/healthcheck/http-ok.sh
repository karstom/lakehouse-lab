#!/bin/bash
# Healthcheck for images without curl/wget (Keycloak): HTTP GET over bash /dev/tcp.
# Succeeds on a 2xx/3xx status line. Usage: http-ok.sh <port> <path>
exec 3<>"/dev/tcp/127.0.0.1/$1" || exit 1
printf 'GET %s HTTP/1.0\r\nHost: localhost\r\n\r\n' "$2" >&3
read -r _ code _ <&3
case "$code" in 2*|3*) exit 0 ;; *) exit 1 ;; esac
