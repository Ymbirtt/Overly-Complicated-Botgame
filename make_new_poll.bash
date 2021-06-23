#!/usr/bin/env bash

cd "$(dirname -- "$0")"
pwd

source venv/bin/activate
echo "Yes please" | python overly_complicated_botgame.py clear_messages > last_run.out
python overly_complicated_botgame.py post_poll_message >> last_run.out

if [ $? -ne 0 ]
then
    notify-send "Overly Complicated Botgame failed for some reason"
fi
