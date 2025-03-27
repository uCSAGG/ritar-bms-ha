#!/usr/bin/with-contenv bashio
set -e
echo "Ritar BMS Service started"

## start ritar-bms web service
python3 -m http.server 50501 -d /web_ui &

## start ritar-bms main part
while true; do
python3 -u ../ritar-bms.py
done


