import configparser
import logging
import random
from collections import defaultdict
from multiprocessing.connection import Listener
from pathlib import Path

import schedule

from Pixiv.Source.pixiv_db import PixivDB
from Pixiv.Source.pixiv_downloader import PixivDownloader


class ImageFetcherService:
    def __init__(self):
        self.logger = logging.getLogger()
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s][Fetcher] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Read config
        config = configparser.ConfigParser()
        config_path = (Path(__file__).parent.absolute() / "config.ini").resolve()
        config.read(str(config_path))

        # Setup Connection
        address = ('localhost', 6000)
        listener = Listener(address, authkey=config["process-communication"]["authkey"].encode())
        self.logger.info("Waiting for connection.." + str(listener.address))
        self.conn = listener.accept()
        self.logger.info("Connection accepted from " + str(listener.last_accepted))

        # Setup Downloader
        self.pixiv_downloader = PixivDownloader(database="Main")
        self.active_downloads_per_minute = int(config["pixiv"]["active_downloads_per_minute"])
        self.idle_downloads_per_minute = int(config["pixiv"]["idle_downloads_per_minute"])
        self.images_per_download = int(config["pixiv"]["images_per_download"])
        self.downloads_left = self.active_downloads_per_minute

        # Keep track of requests and downloads per tag
        self.amount_of_requests = defaultdict(int)
        self.amount_of_downloads = defaultdict(int)
        self.priority_list = []

        # Fetch existing tags and fill the dicts
        pixiv_db = PixivDB(database="Main")
        all_tags: list = pixiv_db.return_all_tags()
        for row in all_tags:
            self.amount_of_requests[row] = 0
            self.amount_of_downloads[row] = 0

        # Keeps track how many requests were made for logging
        self.counter = 0

        # Keep track of whether the bot is ideling
        self.bot_is_active = False

    def start(self):
        schedule.every().minute.do(self.reset_requests_left)

        while True:
            schedule.run_pending()

            tag = self.conn.recv()
            self.logger.info("Received tag " + tag)

            # pixivping just makes sure the scheduled tasks are ran
            if tag == "pixivping":
                continue

            # Non-Ping message received
            self.bot_is_active = True
            self.amount_of_requests[tag] += 1

            # Add new tags to priority list
            self.add_new_tag_to_priority_list(tag)

            # Only request stuff if the limit isnt reached yet
            if self.downloads_left > 0:

                # first check if there are items in the priority list
                if self.priority_list:
                    tag = self.priority_list[0]
                    self.priority_list.remove(tag)
                    self.download_tag(tag)

                else:
                    self.download_tag(tag)

    def add_new_tag_to_priority_list(self, tag: str):
        if tag not in self.priority_list and self.amount_of_downloads[tag] == 0:
            self.priority_list.append(tag)
            self.logger.info("Priority List " + str(self.priority_list))

    def download_tag(self, tag: str):
        self.counter += 1
        self.downloads_left -= 1
        self.amount_of_downloads[tag] += 1

        self.logger.info("Starting download #" + str(self.counter) + " tag " + tag)
        self.pixiv_downloader.add_new_images_to_db(tag, self.images_per_download)

    def reset_requests_left(self):
        # Only fetch images while ideling
        if self.bot_is_active:
            self.logger.info("Did not fetch images while ideling. Bot is active.")
            self.bot_is_active = False
        else:
            self.logger.info("Not used downloads count " + str(self.downloads_left))
            self.logger.info("Priority List " + str(self.priority_list))
            for _ in range(self.idle_downloads_per_minute):
                self.counter += 1
                self.logger.info("Starting download #" + str(self.counter))

                # Prefer using items in priority list over random tags
                if self.priority_list:
                    tag = self.priority_list[0]
                    self.priority_list.remove(tag)
                    self.logger.info("Priority Tag " + tag)
                else:
                    tag = random.choices(list(self.amount_of_requests.keys()),
                                         weights=list(self.amount_of_requests.values()))[0]
                    self.logger.info("Random Tag " + tag)

                self.pixiv_downloader.add_new_images_to_db(tag, self.images_per_download)

        self.logger.info("Reset requests")
        self.downloads_left = self.active_downloads_per_minute


if __name__ == "__main__":
    fetcher = ImageFetcherService()
    fetcher.start()
