import discord
import ruamel.yaml
import asyncio
import parsedatetime
import dateparser
import random
from argparse import ArgumentParser
from texttable import Texttable
from collections import defaultdict
from table_drawer import TableDrawer
from io import BytesIO
from PIL import Image

with open("config.yaml", 'r') as f:
    config = ruamel.yaml.safe_load(f)

TOKEN = config['token']
GUILD_ID = config['guild_id']
CHANNEL_NAME = config['channel_name']
CLIENT = discord.Client()
POLL_TABLE_MARKER = "{polltable}"
CHECK = "✅"
THUMB_UP = "👍"
THUMB_DOWN = "👎"
NEXT_GAME_DATE_STR = "next thursday"
LAST_GAME_DATE_STR = "last thursday"
POLL_MESSAGE_FILE = "poll_messages.yaml"


def get_react_name(react):
    if react.custom_emoji:
        return react.emoji.name
    else:
        return react.emoji


def print_in_box(text):
    table = Texttable()
    table.add_row([text])
    print(table.draw())


def pretty_print_messages(messages):
    table = Texttable()
    for m in messages:
        table.add_row([m.author.name, m.content])
    print(table.draw())


def ask_user_to_select_message(messages):
    print("Please select one of these messages:")
    table = Texttable()
    for n, m in enumerate(messages):
        table.add_row([n, m.author.name, m.content])
    print(table.draw())
    print()

    while in_str := input("> "):
        try:
            in_int = int(in_str)
            if 0 <= in_int < len(messages):
                return messages[in_int]
        except ValueError:
            pass
        print("Invalid input")


def generate_poll_message_body(last_date, next_date):
    with open(POLL_MESSAGE_FILE, 'r') as f:
        content = f.read()
    messages = ruamel.yaml.load(content, Loader=ruamel.yaml.RoundTripLoader)

    def parse_scheduled_message(message_struct):
        dt = dateparser.parse(message_struct["when"])
        return {"when": dt, "message": message_struct["message"]}

    scheduled_messages = messages["scheduled_messages"]

    for msg_index, scheduled_message in enumerate(scheduled_messages):
        when = dateparser.parse(scheduled_message["when"])
        print(last_date)
        print(when)
        print(next_date)
        if last_date < when < next_date:
            message = scheduled_message["message"]
            del messages["scheduled_messages"][msg_index]
            return (message, messages)

    if messages["random_messages"]:
        random_msg_index = random.randint(0, len(messages["random_messages"]))
        message = messages["random_messages"][random_msg_index]
        del messages["random_messages"][random_msg_index]
        return message, messages

    return messages["default_message"], messages


async def generate_text_table(table_data, check_mark=CHECK):
    games = set()
    users = list(table_data.keys())
    for reacts in table_data.values():
        games |= set(reacts)
    games = list(games)
    games.sort(key=get_react_name)
    users.sort(key=lambda x: x.name)

    table = Texttable()
    table.set_cols_align(["r"] + ["c" for _ in users])
    table.set_max_width(10000)

    table.add_row([""] + [a.name for a in users])
    for game in games:
        game_name = get_react_name(game)
        table.add_row([":" + game_name + ":"] + [check_mark if game in table_data[attendee] else "" for attendee in users])

    return table.draw()


async def find_poll_message(messages):
    everyone_messages = await messages.filter(lambda m: m.mention_everyone).flatten()

    if len(everyone_messages) == 1:
        return everyone_messages[0]
    elif len(everyone_messages) == 0:
        raise RuntimeError("Could not find any valid poll message. Did you remember to @everyone?")
    else:
        print("There are several messages which @everyone - which one is the poll message?")
        return ask_user_to_select_message(everyone_messages)


async def generate_poll_data(channel, check_mark=CHECK):
    messages = channel.history(oldest_first=True)

    poll_message = await find_poll_message(messages)

    print("Reading reactions from this message:")
    print_in_box(poll_message.content)
    print()

    thumb_react = discord.utils.get(poll_message.reactions, emoji=THUMB_UP)
    other_reacts = [r for r in poll_message.reactions if r.emoji not in (THUMB_UP, THUMB_DOWN)]

    attendees = await thumb_react.users().flatten()

    table_data = defaultdict(list)
    for react in other_reacts:
        react_users = await react.users().flatten()
        for user in react_users:
            table_data[user].append(react)

    non_voters = set(attendees) - set(table_data.keys())
    for non_voter in non_voters:
        table_data[non_voter] = []

    return table_data


async def find_table_message(channel):
    return await channel.history().filter(lambda m: m.author == CLIENT.user and m.content.startswith(POLL_TABLE_MARKER)).flatten()


async def draw_poll_table(channel):
    table_data = await generate_poll_data(channel)
    table_image = await TableDrawer.default_draw(table_data)
    table_message = await find_table_message(channel)
    table_image_handle = BytesIO()
    table_image.save(table_image_handle, 'PNG')
    table_image_handle.seek(0)

    table_file = discord.File(table_image_handle, "this_weeks_games.png")

    if table_message:
        print("Updating old poll message")
        await table_message[0].delete()
    else:
        print("Posting new poll message")
    await channel.send(POLL_TABLE_MARKER, file=table_file)
    print("Done! Have a nice day 😊")


async def preview_poll_table(channel):
    table_data = await generate_poll_data(channel)
    table_image = await TableDrawer.default_draw(table_data)
    alpha = table_image.getchannel("A")
    bg = Image.new("RGBA", table_image.size, (0, 0, 0, 255))
    bg.paste(table_image, mask=alpha)
    bg.show()


async def print_poll_table(channel):
    table_data = await generate_poll_data(channel)
    print("Here's how it breaks down:")
    print(await generate_text_table(table_data))


async def post_poll_table(channel):
    table_data = await generate_poll_data(channel, check_mark="✔")
    table = await generate_text_table(table_data)

    table_message = find_table_message(channel)

    table_text = POLL_TABLE_MARKER + "\n```\n" + table + "\n```"
    if table_message:
        print("Updating old poll message")
        await table_message[0].edit(content=table_text)
    else:
        print("Posting new poll message")
        await channel.send(table_text)
    print("Done! Have a nice day 😊")


async def clear_messages(channel):
    messages = (await channel.history(oldest_first=True).filter(lambda m: not m.is_system()).flatten())[1:]
    if not messages:
        print("There are no messages for me to delete")
        return

    print("WARNING! This will IRREVERSIBLY DELETE the following messages")
    pretty_print_messages(messages)
    print()
    confirmation_str = "Yes please"
    print("Are you absolutely sure that these are the messages you want to delete?")
    print(f"Input \"{confirmation_str}\" - case sensitive - to confirm")
    in_str = input("> ")
    if in_str == confirmation_str:
        print("OK, deleting")
        for message in messages:
            await message.delete()
        print("Done! Have a nice day 😊")
    else:
        print("Confirmation failed - not deleting")


async def post_poll_message(channel):
    cal = parsedatetime.Calendar()

    last_datetime, ret = cal.parseDT(LAST_GAME_DATE_STR)
    if not ret:
        raise RuntimeError(f"Could not parse {LAST_GAME_DATE_STR} as a datetime")

    next_datetime, ret = cal.parseDT(NEXT_GAME_DATE_STR)
    if not ret:
        raise RuntimeError(f"Could not parse {NEXT_GAME_DATE_STR} as a datetime")

    message_header = "{poll} @everyone"
    message_body, new_messages_content = generate_poll_message_body(last_datetime, next_datetime)
    message_footer = f"**Games? {next_datetime.strftime('%d/%m/%Y')}**"

    message = "\n".join([message_header, message_body, "", message_footer])

    await channel.send(message)

    with open(POLL_MESSAGE_FILE, 'w') as f:
        f.write(ruamel.yaml.dump(new_messages_content, Dumper=ruamel.yaml.RoundTripDumper))


async def run_bot():
    parser = ArgumentParser(description="Do some basic admin in the OCB discord channel")

    action_table = {
        "print_table": print_poll_table,
        "clear_messages": clear_messages,
        "post_table": post_poll_table,
        "draw_table": draw_poll_table,
        "preview_table": preview_poll_table,
        "post_poll_message": post_poll_message,
    }

    parser.add_argument('action', help=f"The action to perform - one of {action_table.keys()}")
    args = parser.parse_args()
    guild = discord.utils.get(CLIENT.guilds, id=GUILD_ID)
    if not guild:
        print("Error: could not find the configured guild - check config.yaml!")

    channel = discord.utils.get(guild.channels, name=CHANNEL_NAME)
    if not channel:
        print("Error: could not find the configured channel - check config.yaml!")

    action_func = action_table.get(args.action)
    if action_func is not None:
        await action_func(channel)
    else:
        print(f"Invalid action - I don't know how to {args.action}")


@CLIENT.event
async def on_ready():
    try:
        await run_bot()
    finally:
        await CLIENT.close()

loop = asyncio.get_event_loop()
loop.set_exception_handler(lambda *x: None)
CLIENT.run(TOKEN)
