import logging
import configparser
from pathlib import Path

from discord.ext import commands

from Cogs.Source.general_cog import General
from Cogs.Source.pixiv_cog import Pixiv

# Setup logger
logger = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][Bot] %(message)s',
    datefmt='%H:%M:%S'
)

# Read config
config = configparser.ConfigParser()
config_path = (Path(__file__).parent.absolute() / "config.ini").resolve()
config.read(str(config_path))

# Setup Metadata
bot = commands.Bot(command_prefix='.')
oauth_token = config['discord']['oauth_token']


@bot.event
async def on_ready():
    logger.info('Logged in as')
    logger.info(bot.user.name)
    logger.info(bot.user.id)
    logger.info('------')


# Disable default help
bot.remove_command('help')

# Register Cogs
bot.add_cog(Pixiv(bot))
bot.add_cog(General(bot))

# Start the bot
bot.run(oauth_token)
