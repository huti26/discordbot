#!/bin/bash
python3 -u ./Bot/Pixiv/Source/pixiv_db_initializer.py

python3 -u ./Bot/image_fetcher.py &
python3 -u ./Bot/discord_bot.py