#!/bin/sh
set -e

pigpiod -l

# wait for pigpio to become ready:
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