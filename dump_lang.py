"""Cetak semua key language pack iOS, buat nyocokin LANG_KEYS di lang.py.

Pakai:  python dump_lang.py id            (atau kode setlang apa pun)
        python dump_lang.py id | grep -i presence
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from lang import fetch_pack

load_dotenv()


async def main(code: str):
    async with TelegramClient(os.getenv("SESSION", "ssip"),
                              int(os.environ["API_ID"]), os.environ["API_HASH"]) as c:
        pack = await fetch_pack(c, code)
        for k, v in sorted(pack.items()):
            print(f"{k} = {v!r}")


asyncio.run(main(sys.argv[1]))
