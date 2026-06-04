#!/bin/sh
set -e

pigpiod -l
python -m control.main