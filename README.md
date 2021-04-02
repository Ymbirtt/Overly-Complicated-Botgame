# Overly Complicated Botgame 🦾🤖

A bot that makes it easier for us to figure out what board games we want to
play.

## Setup

This project was written using Python 3.8.5 - it might work on older versions
but I've not checked. While you don't have to use a virtual environment to
manage its dependencies, I'd strongly recommend using one - `pip install
virtualenv` should install it for you.

You also need to ask me nicely for an API token - the default config should
point correctly at our channel and server, but feel free to change those fields
if you want to run the bot in your own fun channel.

```
$ git clone https://github.com/Ymbirtt/Overly-Complicated-Botgame.git
$ cd overly_complicated_botgame
$ virtualenv venv -p python3
$ source venv/bin/activate
$ pip install -r requirements.txt
$ cp config_example.yaml config.yaml
$ vim config.yaml # Paste in your API token here!
$ python overly_complicated_botgame.py -h
```

If, after a couple of seconds, you find yourself looking at a usage message,
then you're ready to go!

If you're running this on Windows, the virtualenv interface might be a little
different - I'm fairly sure that all you need to do is replace that `$ source`
command with run `> venv\Scripts\activate`, but I haven't tried it.

## Usage

```
$ cd overly_complicated_botgame
$ source venv/bin/activate
$ python overly_complicated_botgame.py print_table
```

OCBot should pick out the correct poll message and dump a nice table into your
terminal.

OCBot will look for the only message in the configured channel with an
`@everyone`. If there are several, the bot will prompt you to pick one. If there
aren't any, the bot will get confused - you should probably edit your message to
tag everyone...

Every week, I've been using the `clear_messages` command to clean up the poll
channel, then posting a new poll message. I have an anacron script which, every
wednesday, uses the `draw_table` command to drop the pretty table into the chat.
If you need to re-make that table for whatever reason, just re-run that command.

The `draw_table` command uses emoji from https://twemoji.twitter.com/. Thanks!
