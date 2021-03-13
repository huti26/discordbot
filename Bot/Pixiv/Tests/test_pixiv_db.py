from unittest import TestCase

from Bot.Pixiv.Source.pixiv_db import PixivDB


class TestPixivDB(TestCase):
    def setUp(self):
        self.db = PixivDB(database="Tests")

    def cleanDBInbetweenTests(self):
        # Delete the tables
        query1 = """
                DROP TABLE Images
                """

        query2 = """
                DROP TABLE Tags
                """

        query3 = """
                DROP TABLE ImageTags
                """

        self.db.cursor.execute(query1)
        self.db.cursor.execute(query2)
        self.db.cursor.execute(query3)
        self.db.connection.commit()

        # Create them again
        query1 = """
                CREATE TABLE IF NOT EXISTS "Images" (
                    "pixiv_image_id"	integer,
                    "file_path"	TEXT NOT NULL,
                    "safety_level"	integer NOT NULL,
                    "artist"	integer NOT NULL,
                    PRIMARY KEY("pixiv_image_id")
                );    
                """

        query2 = """
                CREATE TABLE IF NOT EXISTS "Tags" (
                    "tag_id"	INTEGER,
                    "tag"	TEXT NOT NULL UNIQUE,
                    PRIMARY KEY("tag_id")
                );    
                """

        query3 = """
                CREATE TABLE "ImageTags" (
                    "pixiv_image_id"	INTEGER,
                    "tag_id"	INTEGER,
                    PRIMARY KEY("pixiv_image_id","tag_id")
                );        
                """

        self.db.cursor.execute(query1)
        self.db.cursor.execute(query2)
        self.db.cursor.execute(query3)
        self.db.connection.commit()

    # 3 images
    # image 1: red blue     sfw
    # image 2: green        nsfw
    # image 3: red blue     nsfw
    def insertExampleEntries(self):
        image11 = {
            "file_path": "filepath1",
            "pixiv_image_id": 1,
            "safety_level": 0,
            "artist": 123401,
            "tag": "red"
        }

        image12 = {
            "file_path": "filepath1",
            "pixiv_image_id": 1,
            "safety_level": 0,
            "artist": 123401,
            "tag": "blue"
        }

        image2 = {
            "file_path": "filepath2",
            "pixiv_image_id": 2,
            "safety_level": 1,
            "artist": 123402,
            "tag": "green"
        }

        image31 = {
            "file_path": "filepath3",
            "pixiv_image_id": 3,
            "safety_level": 1,
            "artist": 123403,
            "tag": "red"
        }

        image32 = {
            "file_path": "filepath3",
            "pixiv_image_id": 3,
            "safety_level": 1,
            "artist": 123403,
            "tag": "blue"
        }

        images_to_add = [image11, image11, image12, image2, image31, image32]

        self.db.insert_images(images_to_add)

    def test_inserts(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()
        self.assertTrue(True)

    def test_check_if_image_exists(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        pixiv_id_1_exists: bool = self.db.check_if_image_exists(1)
        pixiv_id_2_exists: bool = self.db.check_if_image_exists(2)
        pixiv_id_4_exists: bool = self.db.check_if_image_exists(4)

        self.assertTrue(pixiv_id_1_exists)
        self.assertTrue(pixiv_id_2_exists)
        self.assertFalse(pixiv_id_4_exists)

    def test_return_all_tags(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        all_tags: list = self.db.return_all_tags()

        self.assertTrue("red" in all_tags)
        self.assertTrue("blue" in all_tags)
        self.assertTrue("green" in all_tags)
        self.assertFalse("yellow" in all_tags)

    def test_return_top_tags(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        top_tags: dict = self.db.return_top_tags()

        self.assertTrue(top_tags["red"] == 2)
        self.assertTrue(top_tags["blue"] == 2)
        self.assertTrue(top_tags["green"] == 1)

    def test_return_image(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        image1_tags_exists: dict = self.db.return_image(tags=["red"], safety_level=1)
        image1_tag_doesnt_exists: dict = self.db.return_image(tags=["yellow"], safety_level=0)
        image2_tags_exists: dict = self.db.return_image(tags=["red", "blue"], safety_level=0)

        self.assertTrue(image1_tags_exists)
        self.assertTrue(image2_tags_exists)
        self.assertFalse(image1_tag_doesnt_exists)

    def test_return_image_count(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        image_count_all = self.db.return_image_count(tags=[])
        image_count_red = self.db.return_image_count(tags=["red"])
        image_count_green = self.db.return_image_count(tags=["green"])
        image_count_red_blue = self.db.return_image_count(tags=["red", "blue"])

        self.assertTrue(image_count_all == 3)
        self.assertTrue(image_count_red == 2)
        self.assertTrue(image_count_green == 1)
        self.assertTrue(image_count_red_blue == 2)

    def test_return_imagetags_row_count(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        row_count = self.db.return_imagetags_row_count()

        self.assertTrue(row_count == 5)

    def test_return_images_row_count(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        row_count = self.db.return_images_row_count()

        self.assertTrue(row_count == 3)

    def test_remove_tag_and_delete_from_file_system(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        self.db.remove_tag_and_delete_from_file_system(tag="red", nsfw_only=True)
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 3)
        self.assertTrue(images_row_count == 2)

        self.db.remove_tag_and_delete_from_file_system(tag="red", nsfw_only=False)
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 1)
        self.assertTrue(images_row_count == 1)

        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        self.db.remove_tag_and_delete_from_file_system(tag="red", nsfw_only=False)
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 1)
        self.assertTrue(images_row_count == 1)

    def test_remove_artist_and_delete_from_file_system(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        self.db.remove_artist_and_delete_from_file_system(artist="123401")
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 3)
        self.assertTrue(images_row_count == 2)

        self.db.remove_artist_and_delete_from_file_system(artist="123402")
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 2)
        self.assertTrue(images_row_count == 1)

    def test_remove_image_and_delete_from_file_system(self):
        self.cleanDBInbetweenTests()
        self.insertExampleEntries()

        self.db.remove_image_and_delete_from_file_system(pixiv_image_id=1)
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 3)
        self.assertTrue(images_row_count == 2)

        self.db.remove_image_and_delete_from_file_system(pixiv_image_id=2)
        imagetags_row_count = self.db.return_imagetags_row_count()
        images_row_count = self.db.return_images_row_count()
        self.assertTrue(imagetags_row_count == 2)
        self.assertTrue(images_row_count == 1)
