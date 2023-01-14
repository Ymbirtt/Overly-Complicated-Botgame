from PIL import Image
from io import BytesIO
import logging
import requests
import math
import os


class TableDrawer:
    use_remote_emoji = False
    emoji_dir = os.path.join("data", "emoji")
    emoji_cdn_base = "https://twemoji.maxcdn.com/v/latest/72x72/"

    def __init__(self, padding_width=10, square_size=128, square_padding=5):
        self.__padding_width = padding_width
        self.__square_size = square_size
        self.__square_padding = square_padding
        self.__image_cache = {}
        self.__log = logging.getLogger(f"ocb.{__name__}")

    @classmethod
    async def default_draw(cls, table_data):
        c = cls()
        return (await c.draw(table_data))

    def table_coords_to_image_coords(self, x, y, image):
        x_out = self.__padding_width + x * (self.__square_size + self.__square_padding) + ((self.__square_size - image.width) // 2)
        y_out = self.__padding_width + y * (self.__square_size + self.__square_padding) + ((self.__square_size - image.height) // 2)
        return x_out, y_out

    def new_image(self, num_cols, num_rows):
        table_width = self.__padding_width + num_cols * (self.__square_size +
                self.__square_padding) + self.__padding_width
        table_height = self.__padding_width + num_rows * (self.__square_size +
                self.__square_padding) + self.__padding_width

        out_image = Image.new("RGBA", size=(table_width, table_height))
        return out_image

    async def image_from_url(self, url):
        if url in self.__image_cache:
            return self.__image_cache[url]

        self.__log.debug(f"Getting image from url {url}")
        try:
            response = requests.get(url)
            http_error = False
        except Exception as e:
            self.__log.error(f"Failed to even get an HTTP response from url {url}!")
            self.__log.exception(e)
            http_error = True

        if http_error or not response.ok:
            image = Image.new('RGBA', (self.__square_size, self.__square_size), "blue")
            if not http_error:
                self.__log.error(f"Failed to get image - got response {response} from url {url}")
        else:
            image = Image.open(BytesIO(response.content))

        image.thumbnail((self.__square_size, self.__square_size))
        image.convert("RGBA")
        self.__image_cache[url] = image
        return self.__image_cache[url]

    async def user_image(self, user):
        self.__log.debug(f"Getting image for user {user}")
        return await self.image_from_url(user.display_avatar.url)

    async def react_image(self, react):
        self.__log.debug(f"Getting image for reaction {react}")
        if react.is_custom_emoji():
            return await self.image_from_url(react.emoji.url)
        else:
            return await self.image_from_emoji(react.emoji)

    async def image_from_emoji(self, emoji):
        hex_codes = [format(ord(ch), 'x') for ch in emoji]
        # Strip out trailing variant specifiers because they break twemoji
        if len(hex_codes) == 2 and hex_codes[-1] == 'fe0f':
            hex_codes = hex_codes[:-1]

        filename = '-'.join(hex_codes) + ".png"

        if self.use_remote_emoji:
            url = self.emoji_cdn_base + filename
            return await self.image_from_url(url)
        else:
            filepath = os.path.join(self.emoji_dir, filename)
            return await self.image_from_file(filepath)

    async def image_from_file(self, filepath):
        self.__log.debug(f"Getting image from path {filepath}")
        try:
            with open(filepath, 'rb') as f:
                image = Image.open(f)
                image.load()
        except Exception as e:
            image = Image.new('RGBA', (self.__square_size, self.__square_size), "blue")
            self.__log.error("Failed to get image from file:")
            self.__log.exception(e)

        image.thumbnail((self.__square_size, self.__square_size))
        image.convert("RGBA")
        return image

    async def draw(self, table_data):
        games = set()
        users = list(table_data.keys())
        for reacts in table_data.values():
            games |= set(reacts)
        games = list(games)
        games.sort(key=lambda game: -len([user for user in users if game in table_data[user]]))
        users.sort(key=lambda user: len(table_data[user]) if len(table_data[user]) > 0 else math.inf)

        num_cols = len(users)
        num_rows = len(games) + 1
        out_image = self.new_image(num_cols, num_rows)

        for col, user in enumerate(users):
            avatar = await self.user_image(user)
            coords = self.table_coords_to_image_coords(col, 0, avatar)
            out_image.paste(avatar, coords)

        for row, game in enumerate(games):
            game_icon = await self.react_image(game)
            # game_icon.show()
            # coords = self.table_coords_to_image_coords(0, row + 1, game_icon)
            # print(f"Drawing in {coords}")
            # out_image.paste(game_icon, coords)

            for col, user in enumerate(users):
                if game in table_data[user]:
                    coords = self.table_coords_to_image_coords(col, row + 1, game_icon)
                    out_image.paste(game_icon, coords)

        return out_image
