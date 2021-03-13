import configparser
import json
import logging
from collections import defaultdict
from pathlib import Path

import schedule
from pixivpy3 import *

from Pixiv.Source.pixiv_db import PixivDB


def list_to_file(file_path: str, line_list: list):
    with open(file_path, "w") as file:
        for line in line_list:
            file.write(line + "\n")


def file_to_list(file_path: str) -> list:
    line_list = []
    with open(file_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            line_list.append(line.rstrip())

    return line_list


# pixiv tags_list are kv pairs of tag:translated_tag
# return True if any tag in the tags_list is part of the blacklist
def tags_in_blacklist(tags: list, blacklist: list) -> bool:
    contains_banned_word = False
    for tag_pair in tags:
        if "name" in tag_pair:
            if tag_pair["name"] in blacklist:
                contains_banned_word = True
        if "translated_name" in tag_pair:
            if tag_pair["translated_name"] in blacklist:
                contains_banned_word = True
    return contains_banned_word


class PixivDownloader:
    def __init__(self, database: str):
        self.logger = logging.getLogger()
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s][Downloader] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Read config
        config = configparser.ConfigParser()
        config_path = (Path(__file__).parent.parent.parent.absolute() / "config.ini").resolve()
        config.read(str(config_path))

        # Login to API
        self.refresh_token = config["pixiv"]["refresh_token"]
        self.api = AppPixivAPI()
        self.api.auth(refresh_token=self.refresh_token)

        # Create Database
        discordbot_dir = Path(__file__).parent.parent.parent.parent.resolve()
        self.images_directory_path = (discordbot_dir / 'DB' / database / 'Images').resolve()
        self.db = PixivDB(database)

        # Setup blacklists
        bot_dir = Path(__file__).parent.parent.parent.resolve()

        self.blacklisted_tags_path = (bot_dir / 'Cogs' / 'Resources' / 'blacklist.txt').resolve()
        self.blacklisted_tags = file_to_list(self.blacklisted_tags_path)

        self.blacklisted_tags_path_nsfw = (bot_dir / 'Cogs' / 'Resources' / 'blacklist-nsfw.txt').resolve()
        self.blacklisted_tags_nsfw = file_to_list(self.blacklisted_tags_path_nsfw)

        self.blacklisted_artists_path = (bot_dir / 'Cogs' / 'Resources' / 'artist-blacklist.txt').resolve()
        self.blacklisted_artists = file_to_list(self.blacklisted_artists_path)

        # Setup offsets
        pixiv_dir = Path(__file__).parent.parent.resolve()
        self.offsets_file_path = (pixiv_dir / 'Resources' / 'offsets.json').resolve()
        with open(self.offsets_file_path) as f:
            self.offsets = defaultdict(int, json.loads(f.read()))

        # schedule events
        schedule.every(1).minutes.do(self.dump_offsets_to_file)  # development
        schedule.every(1).minutes.do(self.update_blacklists)  # development

    def add_new_images_to_db(self, tag: str, amount_of_images_to_download: int):

        try:
            self.logger.info("Offset " + str(self.offsets[tag]))
            response = self.api.search_illust(word=tag, search_target="exact_match_for_tags", offset=self.offsets[tag])

            if "error" in response:
                self.logger.info("Error in response")
                self.logger.info(str(response))

                # refresh login just in case
                self.api.auth(refresh_token=self.refresh_token)

                # offset limit is 5000, just reset it when reached
                if self.offsets[tag] >= 5000:
                    self.logger.info("Reset offset")
                    self.offsets[tag] = 0

                return

            if "illusts" not in response:
                self.logger.info("illusts not in response")
                self.logger.info(str(response))
                return

            illustrations_to_insert = []
            illustration_number = 0

            for illustration in response.illusts:

                # Only download a certain amount of images
                if illustration_number == amount_of_images_to_download:
                    break

                # get relevant info
                pixiv_image_id: str = str(illustration.id)
                safety_level: int = illustration.x_restrict  # 0 -> sfw, 1 -> nsfw, 2 -> nsfl
                artist: str = str(illustration.user.id)

                # check blacklists
                tags: list = illustration.tags

                # blacklisted artists
                if artist in self.blacklisted_artists:
                    self.logger.info("Skipped download " + pixiv_image_id + " due to blacklisted artist.")
                    continue

                # blacklist tags
                if tags_in_blacklist(tags, self.blacklisted_tags):
                    self.logger.info("Skipped download " + pixiv_image_id + " due to completly banned tag.")
                    continue

                # blacklisted tags for nsfw art
                if tags_in_blacklist(tags, self.blacklisted_tags_nsfw) and safety_level == 1:
                    self.logger.info("Skipped download " + pixiv_image_id + " due to nsfw banned tag.")
                    continue

                # Check if it is a multiimage
                # Ignored for now, we only download the first post of a multimage
                # if illustration.metapages:

                fileformat: str = illustration.image_urls.medium.split(".")[-1]
                file_save_name: str = pixiv_image_id + "." + fileformat
                file_path_medium = str(self.images_directory_path) + "/" + pixiv_image_id + "." + fileformat

                # Check if image is already in DB
                in_db = self.db.check_if_image_exists(illustration.id)
                if not in_db:
                    # Download medium
                    try:
                        self.api.download(
                            url=illustration.image_urls.medium,
                            path=self.images_directory_path,
                            name=file_save_name
                        )
                        self.logger.info("Downloaded " + file_save_name)
                    except Exception as e:
                        self.logger.exception(e)
                        self.logger.info("Error when downloading illustration " + file_save_name)
                        break

                    # add a seperate entry for all tags
                    # both englisch and japanese version
                    # we only append, non NULL tags
                    for tag_kv in tags:
                        new_entry_english = {"file_path": file_path_medium, "tag": "",
                                             "pixiv_image_id": illustration.id,
                                             "safety_level": safety_level, "artist": illustration.user.id}

                        new_entry_japanese = {"file_path": file_path_medium, "tag": "",
                                              "pixiv_image_id": illustration.id,
                                              "safety_level": safety_level, "artist": illustration.user.id}

                        if tag_kv["name"] is not None:
                            new_entry_english["tag"] = tag_kv["name"].lower()
                            illustrations_to_insert.append(new_entry_english)

                        if tag_kv["translated_name"] is not None:
                            new_entry_japanese["tag"] = tag_kv["translated_name"].lower()
                            illustrations_to_insert.append(new_entry_japanese)

                else:
                    self.logger.info("Illustration " + file_save_name + " already in DB. Skipping.")

                illustration_number += 1

            # insert all collected entries at once
            self.db.insert_images(illustrations_to_insert)
            self.offsets[tag] += illustration_number
            self.logger.info("Committed downloaded images.")

        except Exception as e:
            self.logger.exception(e)
            self.logger.info("Error when requesting illustrations")

    def dump_offsets_to_file(self):
        self.logger.info("Dumping offsets to file")
        with open(self.offsets_file_path, 'w') as f:
            json.dump(self.offsets, f)

    def update_blacklists(self):
        self.logger.info("Updated blacklisted tags")
        self.blacklisted_tags = file_to_list(self.blacklisted_tags_path)
        self.blacklisted_tags_nsfw = file_to_list(self.blacklisted_tags_path_nsfw)
        self.blacklisted_artists = file_to_list(self.blacklisted_artists_path)
        self.logger.info(str(self.blacklisted_tags))
        self.logger.info(str(self.blacklisted_tags_nsfw))
        self.logger.info(str(self.blacklisted_artists))

    def fetch_single_image_link(self, tag: str, safety_level: int) -> str:
        try:
            response = self.api.search_illust(word=tag, search_target="exact_match_for_tags")

            attempt = 0
            while "error" in response and attempt < 3:
                attempt += 1
                self.logger.info("Error in response")
                self.logger.info(str(response))
                self.api.auth(refresh_token=self.refresh_token)
                response = self.api.search_illust(word=tag, search_target="exact_match_for_tags")

            for illustration in response.illusts:
                if illustration.x_restrict == safety_level:
                    pixiv_image_id: str = str(illustration.id)
                    return "https://www.pixiv.net/en/artworks/" + pixiv_image_id

            else:
                if safety_level == 1:
                    safety_level_text = "nsfw"
                else:
                    safety_level_text = "sfw"
                return "No " + safety_level_text + " images with this tag exist currently."

        except Exception as e:
            self.logger.exception(e)
            self.logger.info("Error when requesting illustrations")
