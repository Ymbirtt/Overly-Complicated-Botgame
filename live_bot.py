import logging
import parsedatetime
import discord
import ruamel.yaml
import dateparser
import random
import json
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
from pprint import pformat
from io import BytesIO
from aio_timers import Timer
from discord.ext import commands

from table_drawer import TableDrawer

discord.VoiceClient.warn_nacl = False


class LiveBot(commands.Bot):
    polling_delay = 10
    poll_tag = "{poll}"
    poll_image_tag = "{poll_image}"
    poll_result_tag = "{poll_result}"
    last_game_date_str = "last thursday"
    next_game_date_str = "next thursday"
    next_poll_date_str = "next friday at 8:00AM"
    thumb_up = "👍"
    thumb_down = "👎"
    poll_message_file = "poll_messages.yaml"

    def __init__(self, guild_id, channel_name, dump_channel_name, role_id, *args, **kwargs):
        self.__guild_id = guild_id
        self.__channel_name = channel_name
        self.__dump_channel_name = dump_channel_name
        self.__role_id = role_id
        self.__log = logging.getLogger(f"ocb.{__name__}")
        self.__guild = None
        self.__channel = None
        self.__dump_channel = None
        self.__poll_timer = None

        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(*args, intents=intents, **kwargs)

    async def __find_poll_message(self):
        everyone_messages = [m async for m in self.__channel.history(oldest_first=True) if self.poll_tag in m.content]

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

        if self.__role_id:
            message_header = f"{self.poll_tag} <@&{self.__role_id}>"
        else:
            message_header = f"{self.poll_tag} @everyone"
        message_body, new_messages_content = self.__generate_poll_message_body(last_datetime, next_datetime)
        message_footer = f"**Games? {next_datetime.strftime('%d/%m/%Y')}**"

        message = "\n".join([message_header, message_body, "", message_footer])

        ret = await self.__channel.send(message)
        try:
            with open(self.poll_message_file, 'w') as f:
                f.write(ruamel.yaml.dump(new_messages_content, Dumper=ruamel.yaml.RoundTripDumper))
        except Exception as e:
            self.__log.error(f"Couldn't open {self.poll_mesage_file} to write the new poll message file")
            self.__log.exception(e)

        return ret

    async def on_raw_reaction_remove(self, reaction_event):
        if reaction_event.message_id != self.__poll_message_id:
            return

        self.__log.info(f"{reaction_event.emoji} removed")
        await self.__handle_reaction_change(reaction_event)

    async def on_raw_reaction_add(self, reaction_event):
        if self.__poll_message_id is None:
            self.__log.warning("Found a reaction, but no poll message exists. Something is going wrong!")

        if reaction_event.message_id != self.__poll_message_id:
            return

        self.__log.info(f"{reaction_event.member.name} reacted with {reaction_event.emoji}")
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
        self.__log.info(f"Got poll data: {poll_data}")

        table_image = await TableDrawer.default_draw(poll_data)
        table_image_handle = BytesIO()
        table_image.save(table_image_handle, 'PNG')
        table_image_handle.seek(0)
        table_file = discord.File(table_image_handle, "this_weeks_games.png")

        embed = discord.Embed()
        message = await self.__dump_channel.send(content=self.poll_image_tag, files=[table_file])
        image_url = message.attachments[0].url
        embed.set_image(url=image_url)

        await poll_message.edit(embed=embed)
        poll_image_messages = [m async for m in
                self.__dump_channel.history(oldest_first=False) if not
                m.is_system() and self.poll_image_tag in m.content][1:]

        self.__log.info(f"Found {len(poll_image_messages)} old poll images - deleting")

        for message in poll_image_messages:
            await message.delete()
        self.__log.info("Poll table successfully updated")

    async def __generate_poll_data(self, poll_message):
        thumb_react = discord.utils.get(poll_message.reactions, emoji=self.thumb_up)
        other_reacts = [r for r in poll_message.reactions if r.emoji not in (self.thumb_up, self.thumb_down)]

        if thumb_react:
            attendees = [u async for u in thumb_react.users()]
        else:
            attendees = []

        self.__log.info(f"Found {len(attendees)} attendees, who want to play {len(other_reacts)} games")

        table_data = defaultdict(list)
        for react in other_reacts:
            react_users = [u async for u in react.users()]
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

        if len(messages["random_messages"]) > 0:
            random_msg_index = random.randint(0, len(messages["random_messages"]))
            message = messages["random_messages"][random_msg_index]
            del messages["random_messages"][random_msg_index]
            return message, messages

        return messages["default_message"], messages

    def __set_reset_timer(self):
        friday = 4  # python day of week constant meanining Friday
        now = datetime.now()
        today = now.date()

        if now.weekday() < friday:
            next_poll_date = today + timedelta(days=friday - today.weekday())
        elif now.weekday() == friday:
            if now.hour < 10:
                next_poll_date = today
            else:
                next_poll_date = today + timedelta(days=7)
        else:  # now.weekday() > friday
            next_poll_date = today + timedelta(days=7 + friday - today.weekday())

        next_poll_datetime = datetime(
            year=next_poll_date.year,
            month=next_poll_date.month,
            day=next_poll_date.day,
            hour=10
        )

        if next_poll_datetime < now:
            self.__log.error(f"Got a negative time until reset. Your logic is wrong somehow! Now is {now}, and I think the next poll should be at {next_poll_datetime} - patching this hole...")
            next_poll_datetime += timedelta(days=7)

        time_until_reset = (next_poll_datetime - datetime.now()).total_seconds()

        self.__reset_timer = Timer(time_until_reset, self.__reset_poll, callback_async=True)
        self.__log.info(f"Set timer to expire at around {next_poll_datetime} - {time_until_reset} seconds from now")

    async def __reset_poll(self):
        self.__log.info("Resetting poll!")

        await self.__stash_results()

        self.__log.info("Deleting old poll")
        messages = [m async for m in self.__channel.history(oldest_first=True)
                if not m.is_system()][1:]
        for message in messages:
            await message.delete()
        self.__poll_message_id = (await self.__create_poll_message()).id
        self.__log.info(f"Created new poll - message ID {self.__poll_message_id}")
        self.__set_reset_timer()

    async def __stash_results(self):
        self.__log.info("Stashing poll results")
        poll_message = await self.__channel.fetch_message(self.__poll_message_id)
        poll_data = await self.__generate_poll_data(poll_message)

        self.__log.info("Logging this poll data:")
        self.__log.info(pformat(poll_data))
        jsonable_poll = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "poll_results": [
                {
                    "user_id": user.id,
                    "votes": [v.emoji.name if v.is_custom_emoji() else v.emoji for v in votes],
                }
                for (user, votes) in poll_data.items()
            ]
        }
        self.__log.info("Logging this data:")
        self.__log.info(str(jsonable_poll))
        json_data = json.dumps(jsonable_poll)

        await self.__dump_channel.send(content="\n".join([self.poll_result_tag, json_data]))

    async def on_ready(self):
        self.__log.info("Connected!")
        self.__poll_message_id = None
        self.__guild = self.get_guild(self.__guild_id)
        channels = self.__guild.channels
        self.__channel = next(c for c in channels if c.name == self.__channel_name)
        self.__dump_channel = next(c for c in channels if c.name == self.__dump_channel_name)
        self.__log.info(f"Running in guild {self.__guild}, channel {self.__channel}, dump channel {self.__dump_channel}")
        poll_message = await self.__find_poll_message()

        if not poll_message:
            self.__log.info("Didn't find a poll message on startup, posting a new one")
            self.__poll_message_id = (await self.__create_poll_message()).id
        elif datetime.now(pytz.utc) - poll_message.created_at > timedelta(days=7):
            self.__poll_message_id = poll_message.id
            self.__log.info("Found a poll message on startup, but it is more than 7 days old - resetting")
            await self.__reset_poll()
        else:
            self.__poll_message_id = poll_message.id
            self.__log.info(f"Found poll message with ID: {self.__poll_message_id}, created {poll_message.created_at}")

        if self.__poll_message_id is None:
            self.__log.critical("Couldn't find a poll message to watch for some reason!")
            raise RuntimeError("Couldn't find poll message")

        if self.__role_id == 0:
            self.__log.info("No role ID set, will ping @everyone")
        else:
            roles = await self.__guild.fetch_roles()
            target_role = next((r for r in roles if r.id == self.__role_id), None)
            if target_role:
                self.__log.info(f"Will notify role @{target_role.name}")
            else:
                self.__log.critical(f"You've asked me to notify role ID {self.__role_id}, but I couldn't find any such role in this guild")
                self.__log.critical("I found the following roles:")
                for role in roles:
                    self.__log.critical(f"{role.id}: {role.name}")
                raise RuntimeError("Could not find role")

        self.__set_reset_timer()
