import logging
from datetime import datetime
from datetime import timedelta

from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger()
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s][Bot] %(message)s',
            datefmt='%H:%M:%S'
        )

        self.star_time = datetime.now().replace(microsecond=0)

    @commands.command(name="uptime")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def return_uptime(self, context):
        time_difference: timedelta = datetime.now().replace(microsecond=0) - self.star_time
        await context.send(str(time_difference))

    @commands.command(name="ping")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ping(self, context):
        await context.send('pong')
