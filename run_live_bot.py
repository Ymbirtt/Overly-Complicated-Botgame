import os
import logging
import coloredlogs
from live_bot import LiveBot

TOKEN = os.environ['OCB_TOKEN']
GUILD_ID = os.environ['OCB_GUILD_ID']
CHANNEL_NAME = os.environ['OCB_CHANNEL_NAME']
DUMP_CHANNEL_NAME = os.environ['OCB_DUMP_CHANNEL_NAME']
ROLE_ID = os.environ.get('OCB_ROLE_ID', 0)
LOG_LEVEL = os.environ.get('OCB_LOG_LEVEL', 'DEBUG')


def main():
    coloredlogs.install(level=LOG_LEVEL, logger=logging.getLogger('ocb'))
    bot = LiveBot(guild_id=int(GUILD_ID),
                  channel_name=CHANNEL_NAME,
                  dump_channel_name=DUMP_CHANNEL_NAME,
                  role_id=int(ROLE_ID),
                  command_prefix='!')
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
