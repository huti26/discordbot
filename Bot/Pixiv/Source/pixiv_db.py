import logging
import sqlite3
from pathlib import Path


class PixivDB:
    def __init__(self, database: str):
        self.logger = logging.getLogger()
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s][Database] %(message)s',
            datefmt='%H:%M:%S'
        )

        discordbot_dir = Path(__file__).parent.parent.parent.parent.resolve()
        db_file_path = (discordbot_dir / 'DB' / database / "pixiv.db").resolve()
        self.connection = sqlite3.connect(str(db_file_path))
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def insert_images(self, images_to_add: list):
        for image in images_to_add:
            self.insert_image_without_commit(file_path=image["file_path"], pixiv_image_id=image["pixiv_image_id"],
                                             tag=image["tag"],
                                             safety_level=image["safety_level"], artist=image["artist"])

        self.connection.commit()

    def insert_image_without_commit(self, file_path: str, pixiv_image_id: int, tag: str,
                                    safety_level: int, artist: int):
        # Insert into Images
        query = """
                INSERT OR IGNORE INTO Images 
                (pixiv_image_id, file_path, safety_level, artist)
                VALUES (?,?,?,?)
                """
        values = [pixiv_image_id, file_path, safety_level, artist]
        self.cursor.execute(query, values)

        # Insert into Tags
        query = """
                INSERT OR IGNORE INTO Tags 
                (tag)
                VALUES (?)
                """
        values = [tag]
        self.cursor.execute(query, values)

        # Get tag_id
        query = """
                SELECT tag_id
                FROM Tags
                WHERE tag = ? 
                """
        values = [tag]
        self.cursor.execute(query, values)
        row = self.cursor.fetchone()
        tag_id = row["tag_id"]

        # Insert into ImageTags
        query = """
                INSERT OR IGNORE INTO ImageTags 
                (tag_id, pixiv_image_id)
                VALUES (?, ?)
                """
        values = [tag_id, pixiv_image_id]
        self.cursor.execute(query, values)

    def check_if_image_exists(self, pixiv_image_id: int) -> bool:
        query = """
                SELECT pixiv_image_id
                FROM Images
                WHERE pixiv_image_id = ?                
                """

        self.cursor.execute(query, [pixiv_image_id])
        data = self.cursor.fetchone()
        if data is None:
            return False
        else:
            return True

    def return_all_tags(self) -> list:
        query = """
                SELECT tag
                FROM TAGS
                """

        self.cursor.execute(query)
        data: list = self.cursor.fetchall()

        all_tags = []

        if data is not None:
            for row in data:
                all_tags.append(row["tag"])

        return all_tags

    def return_top_tags(self):
        query = """
                SELECT tag, count
                FROM Tags
                INNER JOIN (
                    SELECT tag_id, COUNT(*) as count
                    FROM ImageTags 
                    GROUP BY tag_id
                    ORDER BY COUNT(*) DESC     
                    LIMIT 10       
                ) ImageTagsTopTen
                ON Tags.tag_id=ImageTagsTopTen.tag_id
                """
        self.cursor.execute(query)
        data = dict(self.cursor.fetchall())

        return data

    def return_image(self, tags: list, safety_level: int):
        safety_condition = "safety_level = ?"

        if tags:
            where_condition = ""

            for _ in tags:
                where_condition += "tag = ? or "

            # remove last "or "
            where_condition = where_condition[:-3]

            query = f"""
                    SELECT *
                    FROM Images
                    WHERE pixiv_image_id IN (
                        SELECT pixiv_image_id
                        FROM ImageTags
                        WHERE ImageTags.tag_id IN (
                            SELECT tag_id
                            FROM Tags
                            WHERE {where_condition}
                        )
                        GROUP BY pixiv_image_id
                        HAVING COUNT(*) >= ?
                    )
                    AND {safety_condition}
                    ORDER BY RANDOM()
                    LIMIT 1
                    """

            tag_count = len(tags)
            tags.append(tag_count)
            tags.append(safety_level)
            values = tags

        else:
            query = f"""
                    SELECT * 
                    FROM Images
                    WHERE pixiv_image_id IN 
                        (
                        SELECT pixiv_image_id 
                        FROM Images
                        ORDER BY RANDOM() 
                        LIMIT 100
                        )
                    AND safety_level = ?
                    LIMIT 1
                    """

            values = [safety_level]

        self.cursor.execute(query, values)
        data = self.cursor.fetchone()

        if data is not None:
            return dict(data)
        else:
            return {}

    def return_image_count(self, tags: list):

        if tags:
            where_condition = ""

            for _ in tags:
                where_condition += "tag = ? or "

            # remove last "or "
            where_condition = where_condition[:-3]

            query = f"""
                    SELECT COUNT(*) as count
                    FROM(
                        SELECT pixiv_image_id
                        FROM ImageTags
                        WHERE ImageTags.tag_id IN (
                            SELECT tag_id
                            FROM Tags
                            WHERE {where_condition}
                        )
                        GROUP BY pixiv_image_id
                        HAVING COUNT(*) >= ?
                    )
                    """

            tag_count = len(tags)
            tags.append(tag_count)
            values = tags
            self.cursor.execute(query, values)

        else:
            query = f"""
                    SELECT COUNT(*) as count
                    FROM Images
                    """
            self.cursor.execute(query)

        data = dict(self.cursor.fetchone())
        count: int = data["count"]
        return count

    def return_imagetags_row_count(self):
        query = f"""
                SELECT COUNT(*) as count
                FROM ImageTags
                """

        self.cursor.execute(query)
        data = dict(self.cursor.fetchone())
        count: int = data["count"]

        return count

    def return_images_row_count(self):
        query = f"""
                SELECT COUNT(*) as count
                FROM Images
                """

        self.cursor.execute(query)
        data = dict(self.cursor.fetchone())
        count: int = data["count"]

        return count

    def remove_tag_and_delete_from_file_system(self, tag: str, nsfw_only: bool):
        self.logger.info("Deleting all images with tag " + tag)

        # Get images to delete
        if nsfw_only:
            query = """
                    SELECT pixiv_image_id,file_path
                    FROM Images
                    WHERE pixiv_image_id in(
                        SELECT pixiv_image_id
                        FROM ImageTags
                        WHERE ImageTags.tag_id IN (
                            SELECT tag_id
                            FROM Tags
                            WHERE tag = ? AND safety_level = 1
                        )
                    )
                    """

        else:
            query = """
                    SELECT pixiv_image_id,file_path
                    FROM Images
                    WHERE pixiv_image_id in(
                        SELECT pixiv_image_id
                        FROM ImageTags
                        WHERE ImageTags.tag_id IN (
                            SELECT tag_id
                            FROM Tags
                            WHERE tag = ?
                        )
                    )
                    """

        values = [tag]
        self.cursor.execute(query, values)
        rows = self.cursor.fetchall()

        # Filter relevant data
        file_paths = []
        pixiv_image_ids = []
        for row in rows:
            file_paths.append(row["file_path"])
            pixiv_image_ids.append(int(row["pixiv_image_id"]))

        self.delete_images_from_file_system(file_paths)
        self.delete_images_from_database(pixiv_image_ids)

    def remove_artist_and_delete_from_file_system(self, artist: str):
        self.logger.info("Deleting all images with tag " + artist)

        # Get images to delete
        query = """
                SELECT pixiv_image_id,file_path
                FROM Images
                WHERE artist = ?
                """

        values = [artist]
        self.cursor.execute(query, values)
        rows = self.cursor.fetchall()

        # Filter relevant data
        file_paths = []
        pixiv_image_ids = []
        for row in rows:
            file_paths.append(row["file_path"])
            pixiv_image_ids.append(int(row["pixiv_image_id"]))

        self.delete_images_from_file_system(file_paths)
        self.delete_images_from_database(pixiv_image_ids)

    def remove_image_and_delete_from_file_system(self, pixiv_image_id: int):
        self.logger.info("Deleting all image with id " + str(pixiv_image_id))

        # Get images to delete
        query = """
                SELECT pixiv_image_id,file_path
                FROM Images
                WHERE pixiv_image_id = ?
                """

        values = [pixiv_image_id]
        self.cursor.execute(query, values)
        rows = self.cursor.fetchall()

        # Filter relevant data
        file_paths = []
        pixiv_image_ids = []
        for row in rows:
            file_paths.append(row["file_path"])
            pixiv_image_ids.append(int(row["pixiv_image_id"]))

        self.delete_images_from_file_system(file_paths)
        self.delete_images_from_database(pixiv_image_ids)

    def delete_images_from_file_system(self, file_paths: list):
        if file_paths:
            delete_count = 0
            for file_path in file_paths:
                file_to_delete = Path(file_path)
                try:
                    file_to_delete.unlink()
                    delete_count += 1
                    self.logger.info("Deleted " + file_path)
                except FileNotFoundError:
                    self.logger.info(str(FileNotFoundError))
                    self.logger.info("Failed deleting " + file_path)

            self.logger.info("Delete count: " + str(delete_count))
            self.connection.commit()
            self.logger.info("Commited deleting.")

        else:
            self.logger.info("No files to delete from file system")

    def delete_images_from_database(self, pixiv_image_ids: list):
        if pixiv_image_ids:
            where_condition = ""

            for _ in pixiv_image_ids:
                where_condition += "pixiv_image_id = ? or "

            # remove last "or "
            where_condition = where_condition[:-3]

            delete_images_entries = f"""
                    DELETE
                    FROM Images
                    WHERE {where_condition}
                    """

            delete_imagetags_entries = f"""
                    DELETE
                    FROM ImageTags
                    WHERE {where_condition}
                    """

            values = pixiv_image_ids
            self.cursor.execute(delete_images_entries, values)
            self.cursor.execute(delete_imagetags_entries, values)
            self.connection.commit()
            self.logger.info("Commited deleting.")

        else:
            self.logger.info("No files to delete from database")

    def log_debug_info(self):
        self.cursor.execute("SELECT * FROM sqlite_master WHERE type='table'")
        self.logger.info("Table schema")
        results = self.cursor.fetchall()
        for row in results:
            self.logger.info(str(dict(row)))
