import asyncio
import io
import os
import re
import time

from dotenv import load_dotenv
from telethon import TelegramClient, errors, events

import lang
import themes
from fetcher import fetch_profile
from renderer import Renderer

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.getenv("SESSION", "ssip")
BOT_TAG = os.getenv("WATERMARK", "ssip userbot")
COOLDOWN = float(os.getenv("COOLDOWN", "8"))          # detik per pengirim
ALLOWED = {int(x) for x in os.getenv("ALLOWED_CHATS", "").split(",") if x.strip()}

USAGE = (
    "❌ FORMAT SALAH.\n\n"
    "Cara pakai: /ssip @usn\n\n"
    "Tambahin full buat zoom, light buat mode terang, pink buat pink terang, "
    "dark pink buat pink gelap, dark blue buat hitam biru\n"
    "Contoh: /ssip @usn full pink\n\n"
    "🌐 Setlang: tempel link setlang-nya\n"
    "/ssip @usn https://t.me/setlanguage/xxx\n\n"
    "🎨 Theme custom (cuma theme iOS): tempel link theme-nya\n"
    "/ssip @usn https://t.me/addtheme/xxx\n\n"
    "Bisa digabung: /ssip @usn full https://t.me/setlanguage/xxx https://t.me/addtheme/xxx"
)

RE_LANG = re.compile(r"https?://t\.me/setlanguage/([A-Za-z0-9_\-]+)")
RE_THEME = re.compile(r"https?://t\.me/addtheme/([A-Za-z0-9_\-]+)")
RE_USER = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")
KNOWN_WORDS = {"full", "light", "pink", "dark", "blue"}

client = TelegramClient(SESSION, API_ID, API_HASH)
renderer = Renderer()
gate = asyncio.Semaphore(2)       # maksimal 2 render bersamaan
last_used: dict[int, float] = {}


def parse(args: str):
    """Balikin dict opsi, atau None kalau format salah."""
    m_lang, m_theme = RE_LANG.search(args), RE_THEME.search(args)
    rest = RE_THEME.sub(" ", RE_LANG.sub(" ", args)).lower().split()
    if not rest:
        return None
    user = RE_USER.match(rest[0])
    if not user:
        return None
    words = rest[1:]
    if any(w not in KNOWN_WORDS for w in words):
        return None

    phrase = " ".join(w for w in words if w != "full")
    preset = {"": "dark", "dark": "dark", "light": "light", "pink": "pink",
              "dark pink": "dark pink", "pink dark": "dark pink",
              "dark blue": "dark blue", "blue dark": "dark blue"}.get(phrase)
    if preset is None:
        return None
    return {
        "username": user.group(1),
        "full": "full" in words,
        "preset": preset,
        "lang": m_lang.group(1) if m_lang else None,
        "theme": m_theme.group(1) if m_theme else None,
    }


@client.on(events.NewMessage(pattern=r"(?is)^/ssip(?:@\w+)?(?:\s+(.*))?$"))
async def ssip(event):
    if ALLOWED and event.chat_id not in ALLOWED:
        return
    sender = event.sender_id or 0
    now = time.monotonic()
    if now - last_used.get(sender, 0) < COOLDOWN:
        return
    last_used[sender] = now

    opts = parse(event.pattern_match.group(1) or "")
    if not opts:
        return await event.reply(USAGE)

    async with gate:
        try:
            # 1) tema: preset + (opsional) tema custom iOS
            override = None
            if opts["theme"]:
                try:
                    override = await themes.load_custom_theme(client, opts["theme"])
                except Exception:
                    return await event.reply("❌ Link theme tidak valid / bukan theme iOS.")
            theme = themes.build_theme(opts["preset"], override)

            # 2) teks UI: bawaan + (opsional) setlang
            try:
                strings, lang_used = await lang.load_strings(client, opts["lang"])
            except Exception:
                return await event.reply("❌ Link setlang tidak valid.")

            # 3) data profil, murni dari server Telegram
            profile = await fetch_profile(client, opts["username"], strings, theme["dark"])

            # 4) watermark: nama bot + waktu asli + penanda kustomisasi
            tags = []
            if lang_used:
                tags.append("setlang")
            if override:
                tags.append("custom theme")
            mark = f"{BOT_TAG} · {profile['fetched_at'].strftime('%d/%m/%Y %H:%M')}"
            if tags:
                mark += " · " + " + ".join(tags)

            png = await renderer.render(profile, theme, strings, opts["full"], mark)
        except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError, ValueError):
            return await event.reply("❌ Username tidak ditemukan / bukan akun user.")
        except errors.FloodWaitError as e:
            return await event.reply(f"⏳ Kena limit Telegram, coba lagi {e.seconds} detik lagi.")
        except Exception as e:
            return await event.reply(f"❌ Gagal bikin gambar: {type(e).__name__}")

    f = io.BytesIO(png)
    f.name = "ssip.png"
    await event.reply(file=f)
    await asyncio.sleep(1.5)  # jeda kecil biar akun aman


async def main():
    await renderer.start()
    await client.start()
    print("userbot jalan")
    try:
        await client.run_until_disconnected()
    finally:
        await renderer.stop()


if __name__ == "__main__":
    asyncio.run(main())
