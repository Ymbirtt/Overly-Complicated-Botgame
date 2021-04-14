import discord
import yaml
import asyncio
from argparse import ArgumentParser
from texttable import Texttable
from collections import defaultdict
from table_drawer import TableDrawer
from io import BytesIO
from PIL import Image

with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

TOKEN = config['token']
GUILD_ID = config['guild_id']
CHANNEL_NAME = config['channel_name']
CLIENT = discord.Client()
POLL_TABLE_MARKER = "{polltable}"
CHECK = "✅"
THUMB_UP = "👍"
THUMB_DOWN = "👎"


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


async def run_bot():
    parser = ArgumentParser(description="Do some basic admin in the OCB discord channel")

    valid_actions = ["print_table", "clear_messages", "post_table",
            "draw_table", "preview_table"]
    parser.add_argument('action', help=f"The action to perform - one of {valid_actions}")
    args = parser.parse_args()
    guild = discord.utils.get(CLIENT.guilds, id=GUILD_ID)
    if not guild:
        print("Error: could not find the configured guild - check config.yaml!")

    channel = discord.utils.get(guild.channels, name=CHANNEL_NAME)
    if not channel:
        print("Error: could not find the configured channel - check config.yaml!")

    if args.action == "print_table":
        await print_poll_table(channel)
    elif args.action == "post_table":
        await post_poll_table(channel)
    elif args.action == "draw_table":
        await draw_poll_table(channel)
    elif args.action == "preview_table":
        await preview_poll_table(channel)
    elif args.action == "clear_messages":
        await clear_messages(channel)
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
