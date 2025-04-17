#!/usr/bin/with-contenv bashio
set -e
echo "Ritar BMS Service started"

## start ritar-bms main part
python3 -u /ritar-bms.py
