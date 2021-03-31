#!/usr/bin/env bash

cd "$(dirname -- "$0")"
pwd

source venv/bin/activate
python overly_complicated_botgame.py draw_table > last_run.out

if [ $? -ne 0 ]
then
    notify-send "Overly Complicated Botgame failed for some reason"
fi
