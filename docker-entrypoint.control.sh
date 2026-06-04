#!/bin/sh
set -e

rm -f /var/run/pigpio.pid /run/pigpio.pid 2>/dev/null || true

pigpiod -s 10 -t 0 -x -1

# wait for pigpiod to become ready:
for i in 1 2 3 4 5 6 7 8 9 10; do
  if pigs t >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

pigs t >/dev/null 2>&1 || {
  echo "pigpiod did not become ready"
  exit 1
}

exec python -m control.main