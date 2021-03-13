import sqlite3
from pathlib import Path


def initialize_image_table(db_file: str):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # Create Tables
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS "Images" (
            "pixiv_image_id"	integer,
            "file_path"	TEXT NOT NULL,
            "safety_level"	integer NOT NULL,
            "artist"	integer NOT NULL,
            PRIMARY KEY("pixiv_image_id")
        );    
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS "Tags" (
            "tag_id"	INTEGER,
            "tag"	TEXT NOT NULL UNIQUE,
            PRIMARY KEY("tag_id")
        );    
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS "ImageTags" (
            "pixiv_image_id"	INTEGER,
            "tag_id"	        INTEGER,
            PRIMARY KEY("pixiv_image_id","tag_id")
        );        
        """
    )

    # Create Indexes
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS "imagetags_index" ON "ImageTags" (
            "tag_id",
            "pixiv_image_id"
        );    
        """
    )

    c.execute(
        """
        CREATE INDEX IF NOT EXISTS "tags_index" ON "Tags" (
            "tag",
            "tag_id"
        );        
        """
    )

    conn.commit()


def print_schema(db_file: str):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print(c.fetchall())

    c.close()


if __name__ == '__main__':
    discordbot_dir = Path(__file__).parent.parent.parent.parent.resolve()

    # print("pixiv_dir", pixiv_dir)

    db_file_path = (discordbot_dir / 'DB' / 'Main' / 'pixiv.db').resolve()
    db_test_file_path = (discordbot_dir / 'DB' / 'Tests' / 'pixiv.db').resolve()

    # print("db_file_path", db_file_path)

    Path(discordbot_dir / 'DB' / 'Main' / 'Images').mkdir(parents=True, exist_ok=True)
    Path(discordbot_dir / 'DB' / 'Tests' / 'Images').mkdir(parents=True, exist_ok=True)

    initialize_image_table(str(db_file_path))
    initialize_image_table(str(db_test_file_path))

    # print_schema(str(db_file_path))
