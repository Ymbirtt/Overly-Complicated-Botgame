import logging
import coloredlogs
import parsedatetime
import discord
import ruamel.yaml
import dateparser
import random
from datetime import datetime
from collections import defaultdict
from aio_timers import Timer
from io import BytesIO
from discord.ext import commands

from table_drawer import TableDrawer


class LiveBot(commands.Bot):
    polling_delay = 10
    poll_tag = "{poll}"
    last_game_date_str = "last thursday"
    next_game_date_str = "next thursday"
    next_poll_date_str = "next friday at 8:00AM"
    thumb_up = "👍"
    thumb_down = "👎"
    poll_message_file = "poll_messages.yaml"

    def __init__(self, guild_id, channel_name, dump_channel_name, *args, **kwargs):
        self.__guild_id = guild_id
        self.__channel_name = channel_name
        self.__dump_channel_name = dump_channel_name
        self.__log = logging.getLogger(__name__)
        self.__guild = None
        self.__channel = None
        self.__dump_channel = None
        self.__poll_timer = None
        coloredlogs.install(level='DEBUG', logger=self.__log)
        super().__init__(*args, **kwargs)

    async def __find_poll_message(self):
        everyone_messages = await \
            self.__channel.history(oldest_first=True)\
            .filter(lambda m: m.mention_everyone and self.poll_tag in m.content)\
            .flatten()

        if len(everyone_messages) == 1:
            return everyone_messages[0]
        elif len(everyone_messages) == 0:
            return None
        else:
            ret = everyone_messages[0]
            self.__log.warning(f"Found several possible poll messages, will guess at this one: {ret}")
            return ret

    async def __create_poll_message(self):
        cal = parsedatetime.Calendar()

        last_datetime, ret = cal.parseDT(self.last_game_date_str)
        if not ret:
            raise RuntimeError(f"Could not parse {self.last_game_date_str} as a datetime")

        next_datetime, ret = cal.parseDT(self.next_game_date_str)
        if not ret:
            raise RuntimeError(f"Could not parse {self.next_game_date_str} as a datetime")

        message_header = f"{self.poll_tag} @everyone"
        message_body, new_messages_content = self.__generate_poll_message_body(last_datetime, next_datetime)
        message_footer = f"**Games? {next_datetime.strftime('%d/%m/%Y')}**"

        message = "\n".join([message_header, message_body, "", message_footer])

        ret = await self.__channel.send(message)
        with open(self.poll_message_file, 'w') as f:
            f.write(ruamel.yaml.dump(new_messages_content, Dumper=ruamel.yaml.RoundTripDumper))

        return ret

    async def on_raw_reaction_remove(self, reaction_event):
        if reaction_event.message_id != self.__poll_message_id:
            return

        self.__log.debug(f"{reaction_event.emoji} removed")
        await self.__handle_reaction_change(reaction_event)

    async def on_raw_reaction_add(self, reaction_event):
        if reaction_event.message_id != self.__poll_message_id:
            return

        self.__log.debug(f"{reaction_event.member.name} reacted with {reaction_event.emoji}")
        await self.__handle_reaction_change(reaction_event)

    async def __handle_reaction_change(self, reaction_event):
        if reaction_event.message_id != self.__poll_message_id:
            return

        if self.__poll_timer:
            self.__poll_timer.cancel()

        self.__poll_timer = Timer(self.polling_delay, self.__update_poll_table, callback_async=True)

    async def __update_poll_table(self):
        self.__log.info("Updating poll table now")
        poll_message = await self.__channel.fetch_message(self.__poll_message_id)
        poll_data = await self.__generate_poll_data(poll_message)
        self.__log.debug(f"Got poll data: {poll_data}")

        table_image = await TableDrawer.default_draw(poll_data)
        table_image_handle = BytesIO()
        table_image.save(table_image_handle, 'PNG')
        table_image_handle.seek(0)
        table_file = discord.File(table_image_handle, "this_weeks_games.png")

        embed = discord.Embed()
        message = await self.__dump_channel.send(files=[table_file])
        image_url = message.attachments[0].url
        embed.set_image(url=image_url)

        await poll_message.edit(embed=embed)
        dump_messages = (await self.__dump_channel.
                                    history(oldest_first=True).
                                    filter(lambda m: not m.is_system()).
                                    flatten()
                        )[:-1]
        for message in dump_messages:
            await message.delete()
        self.__log.info("Poll table successfully updated")

    async def __generate_poll_data(self, poll_message):
        thumb_react = discord.utils.get(poll_message.reactions, emoji=self.thumb_up)
        other_reacts = [r for r in poll_message.reactions if r.emoji not in (self.thumb_up, self.thumb_down)]

        if thumb_react:
            attendees = await thumb_react.users().flatten()
        else:
            attendees = []

        self.__log.info(f"Found {len(attendees)} attendees, who want to play {len(other_reacts)} games")

        table_data = defaultdict(list)
        for react in other_reacts:
            react_users = await react.users().flatten()
            for user in react_users:
                table_data[user].append(react)

        non_voters = set(attendees) - set(table_data.keys())
        for non_voter in non_voters:
            table_data[non_voter] = []

        return table_data

    def __generate_poll_message_body(self, last_date, next_date):
        with open(self.poll_message_file, 'r') as f:
            content = f.read()
        messages = ruamel.yaml.load(content, Loader=ruamel.yaml.RoundTripLoader)

        def parse_scheduled_message(message_struct):
            dt = dateparser.parse(message_struct["when"])
            return {"when": dt, "message": message_struct["message"]}

        scheduled_messages = messages["scheduled_messages"]

        for msg_index, scheduled_message in enumerate(scheduled_messages):
            when = dateparser.parse(scheduled_message["when"])
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

    def __set_reset_timer(self):
        cal = parsedatetime.Calendar()
        next_datetime, ret = cal.parseDT(self.next_poll_date_str)
        if not ret:
            raise RuntimeError(f"Could not parse {self.next_game_date_str} as a datetime")

        time_until_reset = (next_datetime - datetime.now()).total_seconds()
        self.__reset_timer = Timer(time_until_reset, self.__reset_poll, callback_async=True)
        self.__log.info(f"Set timer to expire at around {next_datetime} - {time_until_reset} seconds from now")

    async def __reset_poll(self):
        self.__log.info("Resetting poll")
        messages = (await self.__channel.history(oldest_first=True).filter(lambda m: not m.is_system()).flatten())[1:]
        for message in messages:
            await message.delete()
        self.__poll_message_id = (await self.__create_poll_message()).id
        self.__set_reset_timer()

    async def on_ready(self):
        self.__log.info("Connected!")
        self.__guild = self.get_guild(self.__guild_id)
        channels = self.__guild.channels
        self.__channel = next(c for c in channels if c.name == self.__channel_name)
        self.__dump_channel = next(c for c in channels if c.name == self.__dump_channel_name)
        self.__log.info(f"Running in guild {self.__guild}, channel {self.__channel}, dump channel {self.__dump_channel}")
        poll_message = await self.__find_poll_message()

        if poll_message:
            self.__poll_message_id = poll_message.id
            self.__log.info(f"Found poll message with ID: {self.__poll_message_id}")
        else:
            self.__log.info("Didn't find a poll message on startup, posting a new one")
            self.__poll_message_id = (await self.__create_poll_message()).id

        if self.__poll_message_id is None:
            self.__log.critical("Couldn't find a poll message to watch for some reason!")
            raise RuntimeError("Couldn't find poll message")

        self.__set_reset_timer()
