import os
from live_bot import LiveBot

TOKEN = os.environ['OCB_TOKEN']
GUILD_ID = os.environ['OCB_GUILD_ID']
CHANNEL_NAME = os.environ['OCB_CHANNEL_NAME']
DUMP_CHANNEL_NAME = os.environ['OCB_DUMP_CHANNEL_NAME']


def main():
    # logging.basicConfig(level=logging.DEBUG)
    bot = LiveBot(guild_id=int(GUILD_ID),
                  channel_name=CHANNEL_NAME,
                  dump_channel_name=DUMP_CHANNEL_NAME,
                  command_prefix='!')
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
