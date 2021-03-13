import configparser
import logging
import time
from multiprocessing.connection import Client
from pathlib import Path

import discord
from discord.ext import commands, tasks

from Pixiv.Source.pixiv_db import PixivDB
from Pixiv.Source.pixiv_downloader import PixivDownloader


def file_to_list(file_path: str) -> list:
    line_list = []
    with open(file_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            line_list.append(line.rstrip())

    return line_list


def list_to_file(file_path: str, line_list: list):
    with open(file_path, "w") as file:
        for line in line_list:
            file.write(line + "\n")


class Pixiv(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger()
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s][Bot] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Read config
        config = configparser.ConfigParser()
        config_path = (Path(__file__).parent.parent.parent.absolute() / "config.ini").resolve()
        config.read(str(config_path))

        # Setup db
        self.pixiv_db = PixivDB(database="Main")

        # Setup pixivdownloader
        self.pixiv_downloader = PixivDownloader(database="Main")

        # needed paths
        cogs_folder_path = str(Path(__file__).parent.parent.absolute())

        # init admin list
        admin_ids_file_path = cogs_folder_path + "/Resources/admins.txt"
        self.admin_ids = file_to_list(admin_ids_file_path)
        self.logger.info("Admins: " + str(self.admin_ids))

        # Setup blacklists
        self.blacklisted_tags_path = cogs_folder_path + "/Resources/blacklist.txt"
        self.blacklisted_tags = file_to_list(self.blacklisted_tags_path)
        self.logger.info("Blacklisted tags: " + str(self.blacklisted_tags))

        self.blacklisted_tags_nsfw_path = cogs_folder_path + "/Resources/blacklist-nsfw.txt"
        self.blacklisted_tags_nsfw = file_to_list(self.blacklisted_tags_nsfw_path)
        self.logger.info("NSFW Blacklisted tags: " + str(self.blacklisted_tags_nsfw))

        self.blacklisted_artists_path = cogs_folder_path + "/Resources/artist-blacklist.txt"
        self.blacklisted_artists = file_to_list(self.blacklisted_artists_path)
        self.logger.info("Blacklisted Artists: " + str(self.blacklisted_artists))

        # Setup reports
        self.image_reports_path = cogs_folder_path + "/Resources/reports.txt"
        self.image_reports = file_to_list(self.image_reports_path)
        self.logger.info("Reported tags: " + str(self.image_reports))

        # make sure the fetcher is ready
        time.sleep(3)
        address = ('localhost', 6000)
        self.logger.info("attempting to connect to.." + str(address))
        self.conn = Client(address, authkey=config["process-communication"]["authkey"].encode())

        self.fetcher_ping.start()

    @tasks.loop(seconds=65)
    async def fetcher_ping(self):
        self.logger.info("Sent ping to the Pixiv Image Fetcher.")
        self.conn.send("pixivping")

    #########################################################
    # BASIC SETUP
    #########################################################

    def is_admin(self, author_id: int):
        self.logger.info("Testing admin " + str(author_id) + " " + str(str(author_id) in self.admin_ids))
        return str(author_id) in self.admin_ids

    @commands.group()
    async def pixiv(self, context):
        if context.invoked_subcommand is None:
            await context.send('Invalid pixiv command. Type .pixiv help for more info.')

    #########################################################
    # USER FUNCTIONS
    #########################################################

    @pixiv.command(name="help", brief="Print help text.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def help(self, context):
        embed = discord.Embed(title="Commands", description="Pixiv")

        embed.add_field(name="[.p | .pn] [tags]",
                        value="Posts an image from pixiv, .p posts sfw tagged images and .pn nsfw tagged images. Optionally you can add a list of tags like in the following example.",
                        inline=False)

        embed.add_field(name=""".p miku "ice cream" """,
                        value="""This request would fetch an image that is both tagged as "miku" and as "ice cream". If a tag consists of multiple words, it has to be wrappen by "". Tags on pixiv are case insensitive.""",
                        inline=False)

        embed.add_field(name=".pixiv database [tags]",
                        value="Returns how many there are in the database with the given tags.",
                        inline=False)

        embed.add_field(name=".pixiv report [image_id] [reason]",
                        value="Report any images which you think the bot should not post. Artists can be blacklisted completely as a result. Example usage: .pixiv report 123456 The artist posts gore under sfw",
                        inline=False)

        await context.send(embed=embed)

        if self.is_admin(context.author.id):
            embed = discord.Embed(title="Admin Commands", description="Pixiv")

            embed.add_field(name=".pixiv blacklist [tag | nsfw_tag | artist]",
                            value="Removes all matching entries from the database and filesystem. Does not allow any images to be downloaded in the future, that match the blacklisted item.",
                            inline=False)

            embed.add_field(name=".pixiv whitelist [tag | nsfw_tag | artist]",
                            value="Removes an item from the blacklist and allows future downloads.",
                            inline=False)

            embed.add_field(name="tag",
                            value="If a tag is blacklisted, no image tagged as such will be downloaded.",
                            inline=False)

            embed.add_field(name="nsfw_tag",
                            value="If a nsfw_tag is blacklisted, no nsfw image tagged as such will be downloaded.",
                            inline=False)

            embed.add_field(name="artist",
                            value="If an artist is blacklisted, none of their art will be downloaded.",
                            inline=False)

            embed.add_field(name=".pixiv check_reports",
                            value="Prints all reports.",
                            inline=False)

            embed.add_field(name=".pixiv wipe_reports",
                            value="Wipes all reports.",
                            inline=False)

            await context.send(embed=embed)

    @commands.command(name="p", brief="Fetch a sfw picture.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pixiv_multitag_image(self, context, *tags_tuple: tuple):
        if tags_tuple != ():

            tags_list = []
            tags_string = ""
            for tag_seperated_by_char in tags_tuple:
                tag = ''.join(tag_seperated_by_char)
                tag = tag.lower()
                tags_list.append(tag)
                tags_string += " " + tag

            # remove whitespace at start
            tags_string = tags_string[1:]

            self.logger.info(str(tags_list))
            self.logger.info("Sent " + tags_string + " to fetcher.")
            self.conn.send(tags_string)

            image_data = self.pixiv_db.return_image(tags=tags_list, safety_level=0)

            if "file_path" not in image_data:
                self.logger.info("No image for " + tags_string + " in database")
                image_link: str = self.pixiv_downloader.fetch_single_image_link(tag=tags_string, safety_level=0)
                await context.send(image_link)
            else:
                await context.send(file=discord.File(image_data["file_path"]),
                                   content=str(image_data["pixiv_image_id"]))

        else:
            image_data = self.pixiv_db.return_image(tags=[], safety_level=0)
            await context.send(file=discord.File(image_data["file_path"]),
                               content=str(image_data["pixiv_image_id"]))

    @commands.command(name="pn", brief="Fetch a nsfw picture.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pixiv_multitag_image_nsfw(self, context, *tags_tuple: tuple):
        if tags_tuple != ():

            tags_list = []
            tags_string = ""
            for tag_seperated_by_char in tags_tuple:
                tag = ''.join(tag_seperated_by_char)
                tag = tag.lower()
                tags_list.append(tag)
                tags_string += " " + tag

            # remove whitespace at start
            tags_string = tags_string[1:]

            self.logger.info(str(tags_list))
            self.logger.info("Sent " + tags_string + " to fetcher.")
            self.conn.send(tags_string)

            image_data = self.pixiv_db.return_image(tags=tags_list, safety_level=1)

            if "file_path" not in image_data:
                self.logger.info("No image for " + tags_string + " in database")
                image_link: str = self.pixiv_downloader.fetch_single_image_link(tag=tags_string, safety_level=1)
                await context.send(image_link)
            else:
                await context.send(file=discord.File(image_data["file_path"]),
                                   content=str(image_data["pixiv_image_id"]))

        else:
            image_data = self.pixiv_db.return_image(tags=[], safety_level=1)
            await context.send(file=discord.File(image_data["file_path"]),
                               content=str(image_data["pixiv_image_id"]))

    @pixiv.command(name="toptags", brief="Top 10 tags in the database.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def top_tags(self, context):
        data = self.pixiv_db.return_top_tags()
        response = discord.Embed(title="Top Tags")

        for db_entries, tag in data.items():
            response.add_field(name=tag, value=db_entries, inline=False)

        await context.send(embed=response)

    #########################################################
    # DATABASE STATS FUNCTIONS
    #########################################################

    @pixiv.group(name="database", brief="Return how many entries in the db there are.", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def database(self, context, *tags_tuple: tuple):
        if context.invoked_subcommand is None:
            if tags_tuple != ():
                tags_list = []
                for tag_seperated_by_char in tags_tuple:
                    tag = ''.join(tag_seperated_by_char)
                    tag = tag.lower()
                    tags_list.append(tag)

                image_count = self.pixiv_db.return_image_count(tags_list)
                await context.send(str(image_count))

            else:
                image_count = self.pixiv_db.return_image_count([])
                await context.send(str(image_count))

    #########################################################
    # REPORT FUNCTIONS
    #########################################################

    @pixiv.command(name="report", brief="Report an image for review.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def report_tag(self, context, *user_input_tuples: tuple):
        if user_input_tuples == ():
            await context.send("No empty reports.")

        else:
            user_input = ""
            for user_input_tuple in user_input_tuples:
                user_input += " " + ''.join(user_input_tuple)
            self.image_reports.append(user_input)
            list_to_file(file_path=self.image_reports_path,
                         line_list=self.image_reports)

            await context.send("Successfully reported the image, thanks!")

    @pixiv.command(name="check_reports", hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def check_reports(self, context):
        if self.is_admin(context.author.id):
            if not self.image_reports:
                await context.send("No reports.")
            else:
                embed = discord.Embed(title="Reports", description="")

                for report in self.image_reports:
                    report_split: list = report.split(" ")
                    image_id: str = "Image ID: " + ''.join(report_split[0])
                    reason: str = "Reason: " + ''.join(report_split[1:])
                    embed.add_field(name=image_id, value=reason, inline=False)

                await context.send(embed=embed)

    @pixiv.command(name="wipe_reports", hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wipe_reports(self, context):
        if self.is_admin(context.author.id):
            self.image_reports = []
            list_to_file(file_path=self.image_reports_path, line_list=self.image_reports)
            await context.send("Cleared all reports.")

    #########################################################
    # BLACKLIST WHITELIST FUNCTIONS
    #########################################################

    @pixiv.group()
    async def blacklist(self, context):
        if context.invoked_subcommand is None:
            await context.send('Invalid blacklist command.')

    @pixiv.group()
    async def whitelist(self, context):
        if context.invoked_subcommand is None:
            await context.send('Invalid whitelist command.')

    # update blacklist and save it to file
    def add_item_to_blacklist(self, item: str, blacklist: list, blacklist_path: str, blacklist_name: str) -> bool:
        if item not in blacklist:
            blacklist.append(item)
            list_to_file(blacklist_path, blacklist)
            self.logger.info("Added " + item + " to " + blacklist_name)
            self.logger.info(str(blacklist))
            return True
        else:
            self.logger.info(item + " already in blacklist.")
            self.logger.info(str(blacklist))
            return False

    # remove item from blacklist and save it to file
    def remove_item_from_blacklist(self, item: str, blacklist: list, blacklist_path: str, blacklist_name: str) -> bool:
        if item in blacklist:
            blacklist.remove(item)
            list_to_file(blacklist_path, blacklist)
            self.logger.info("Removed " + item + " from " + blacklist_name)
            self.logger.info(str(blacklist))
            return True
        else:
            self.logger.info(item + " not in nsfw blacklist.")
            self.logger.info(str(blacklist))
            return False

    @blacklist.command(name="image", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def blacklist_image(self, context, pixiv_image_id: int):
        if self.is_admin(context.author.id):
            self.pixiv_db.remove_image_and_delete_from_file_system(pixiv_image_id)
            await context.send("Removed " + str(pixiv_image_id) + " from the database.")

    @blacklist.command(name="tag", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def blacklist_tag(self, context, tag: str):
        tag = tag.lower()
        if self.is_admin(context.author.id):
            self.pixiv_db.remove_tag_and_delete_from_file_system(tag, nsfw_only=False)
            success = self.add_item_to_blacklist(item=tag,
                                                 blacklist=self.blacklisted_tags,
                                                 blacklist_path=self.blacklisted_tags_path,
                                                 blacklist_name="tag blacklist")

            if success:
                await context.send("Added " + tag + " to blacklist.")
            else:
                await context.send(tag + " already in blacklist.")

    @whitelist.command(name="tag", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def whitelist_tag(self, context, tag: str):
        tag = tag.lower()
        if self.is_admin(context.author.id):
            success = self.remove_item_from_blacklist(item=tag,
                                                      blacklist=self.blacklisted_tags,
                                                      blacklist_path=self.blacklisted_tags_path,
                                                      blacklist_name="tag blacklist")

            if success:
                await context.send("Removed " + tag + " from blacklist.")
            else:
                await context.send(tag + " not in blacklist.")

    @blacklist.command(name="nsfw_tag", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def blacklist_nsfw_tag(self, context, tag: str):
        tag = tag.lower()
        if self.is_admin(context.author.id):
            self.pixiv_db.remove_tag_and_delete_from_file_system(tag, nsfw_only=True)
            success = self.add_item_to_blacklist(item=tag,
                                                 blacklist=self.blacklisted_tags_nsfw,
                                                 blacklist_path=self.blacklisted_tags_nsfw_path,
                                                 blacklist_name="nsfw tag blacklist")

            if success:
                await context.send("Added " + tag + " to nsfw blacklist.")
            else:
                await context.send(tag + " already in nsfw blacklist.")

    @whitelist.command(name="nsfw_tag", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def whitelist_nsfw_tag(self, context, tag: str):
        tag = tag.lower()
        if self.is_admin(context.author.id):
            success = self.remove_item_from_blacklist(item=tag,
                                                      blacklist=self.blacklisted_tags_nsfw,
                                                      blacklist_path=self.blacklisted_tags_nsfw_path,
                                                      blacklist_name="nsfw tag blacklist")

            if success:
                await context.send("Removed " + tag + " from nsfw blacklist.")
            else:
                await context.send(tag + " not in nsfw blacklist.")

    @blacklist.command(name="artist", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def blacklist_artist(self, context, artist: str):
        artist = artist.lower()
        if self.is_admin(context.author.id):
            self.pixiv_db.remove_artist_and_delete_from_file_system(artist)
            success = self.add_item_to_blacklist(item=artist,
                                                 blacklist=self.blacklisted_artists,
                                                 blacklist_path=self.blacklisted_artists_path,
                                                 blacklist_name="artist blacklist")

            if success:
                await context.send("Added artist to blacklist.")
            else:
                await context.send("Artist already in blacklist.")

    @whitelist.command(name="artist", hidden=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def whitelist_artist(self, context, artist: str):
        artist = artist.lower()
        if self.is_admin(context.author.id):
            success = self.remove_item_from_blacklist(item=artist,
                                                      blacklist=self.blacklisted_artists,
                                                      blacklist_path=self.blacklisted_artists_path,
                                                      blacklist_name="artist blacklist")

            if success:
                await context.send("Removed artist from blacklist.")
            else:
                await context.send("Artist not in blacklist.")

    #########################################################
    # DEBUG FUNCTIONS
    #########################################################

    @pixiv.command(name="rows", hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rows(self, context):
        if self.is_admin(context.author.id):
            await context.send(str(self.pixiv_db.return_imagetags_row_count()))

    @pixiv.command(name="debug", hidden=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def debug(self, context):
        if self.is_admin(context.author.id):
            self.pixiv_db.log_debug_info()
