"""Ambil data profil. Semua isi berasal dari server Telegram, bukan dari input user.

Bagian yang bergantung layer API baru (musik, gift, warna profil, emoji pattern)
dibungkus try/except: kalau versi Telethon kamu belum mendukung, bagian itu
dilewati dan sisanya tetap jalan.
"""
import base64
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    WIB = ZoneInfo("Asia/Jakarta")
except Exception:  # tzdata belum terpasang -> fallback UTC+7
    WIB = timezone(timedelta(hours=7))

from telethon import types
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetCustomEmojiDocumentsRequest
from telethon.tl.functions.users import GetFullUserRequest


def data_uri(b: bytes | None) -> str | None:
    if not b:
        return None
    if b[:4] == b"RIFF":
        mime = "image/webp"
    elif b[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif b[:4] == b"\x89PNG":
        mime = "image/png"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


def _c(i: int) -> str:
    return f"#{i & 0xFFFFFF:06x}"


async def _thumb(client, doc):
    try:
        return data_uri(await client.download_media(doc, file=bytes, thumb=-1))
    except Exception:
        return None


def presence(status, L: dict) -> str:
    if isinstance(status, types.UserStatusOnline):
        return L["online"]
    if isinstance(status, types.UserStatusRecently):
        return L["recently"]
    if isinstance(status, types.UserStatusLastWeek):
        return L["lastweek"]
    if isinstance(status, types.UserStatusLastMonth):
        return L["lastmonth"]
    if isinstance(status, types.UserStatusOffline):
        seen = status.was_online.astimezone(WIB)
        today = datetime.now(WIB).date()
        if seen.date() == today:
            return f"{L['lastseen']} today at {seen:%H:%M}"
        if (today - seen.date()).days == 1:
            return f"{L['lastseen']} yesterday at {seen:%H:%M}"
        return f"{L['lastseen']} {seen:%d.%m.%y}"
    return L["longago"]


async def _profile_gradient(client, pc, dark: bool):
    """Warna header dari profile_color (PeerColor). None kalau tak tersedia."""
    try:
        from telethon.tl.functions.help import GetPeerProfileColorsRequest
        res = await client(GetPeerProfileColorsRequest(hash=0))
        for opt in res.colors:
            if opt.color_id == pc.color:
                s = opt.dark_colors if (dark and opt.dark_colors) else opt.colors
                cols = getattr(s, "bg_colors", None) or getattr(s, "palette_colors", None)
                if cols:
                    cols = [_c(x) for x in cols]
                    return f"linear-gradient(180deg, {cols[0]}, {cols[-1]})"
    except Exception:
        pass
    return None


async def _emoji_pattern(client, emoji_id):
    try:
        docs = await client(GetCustomEmojiDocumentsRequest(document_id=[emoji_id]))
        return await _thumb(client, docs[0]) if docs else None
    except Exception:
        return None


def _audio_info(doc):
    for a in getattr(doc, "attributes", None) or []:
        if isinstance(a, types.DocumentAttributeAudio):
            return {"title": a.title or "", "artist": a.performer or ""}
    return None


async def _music(client, input_user, fu):
    # 1) field langsung di UserFull (layer API baru)
    info = _audio_info(getattr(fu, "saved_music", None))
    if info:
        return info
    # 2) cadangan: request khusus
    try:
        from telethon.tl.functions.users import GetSavedMusicRequest
        res = await client(GetSavedMusicRequest(id=input_user, offset=0, limit=1))
        for doc in res.documents:
            info = _audio_info(doc)
            if info:
                return info
    except Exception as e:
        print("[music] gagal:", repr(e))
    return None


def short_date(d) -> str:
    d = d.astimezone(WIB)
    return f"{d:%d/%m}" if d.year == datetime.now(WIB).year else f"{d:%d/%m/%y}"


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_birthday(b):
    if not b:
        return None
    s = f"{b.day} {MONTHS[b.month - 1]}"
    year = getattr(b, "year", None)
    if year:
        today = datetime.now(WIB).date()
        age = today.year - year - ((today.month, today.day) < (b.month, b.day))
        s += f" {year} ({age} years old)"
    return s


async def _gifts(client, input_user, limit=6):
    out = []
    try:
        from telethon.tl.functions.payments import GetSavedStarGiftsRequest
        res = await client(GetSavedStarGiftsRequest(peer=input_user, offset="", limit=limit))
        for g in res.gifts:
            gift = g.gift
            doc = getattr(gift, "sticker", None)
            if doc is None:  # gift unik: ambil dari atribut model
                for at in getattr(gift, "attributes", []) or []:
                    doc = getattr(at, "document", None)
                    if doc is not None:
                        break
            if doc is not None:
                img = await _thumb(client, doc)
                if img:
                    out.append(img)
    except Exception:
        pass
    return out


async def _personal_channel(client, fu, full):
    cid = getattr(fu, "personal_channel_id", None)
    if not cid:
        return None
    try:
        ch = next(c for c in full.chats if c.id == cid)
        fc = await client(GetFullChannelRequest(ch))
        msgs = await client.get_messages(ch, limit=1)
        last = msgs[0] if msgs else None
        return {
            "title": ch.title,
            "subs": fc.full_chat.participants_count,
            "photo": data_uri(await client.download_profile_photo(ch, file=bytes)),
            "text": (last.message or "")[:60] if last else "",
            "date": short_date(last.date) if last else "",
        }
    except Exception:
        return None


async def fetch_profile(client, username: str, L: dict, dark: bool) -> dict:
    entity = await client.get_entity(username)
    if not isinstance(entity, types.User):
        raise ValueError("bukan akun user")

    input_user = await client.get_input_entity(entity)
    full = await client(GetFullUserRequest(entity))
    fu = full.full_user

    handles = []
    if entity.username:
        handles.append(entity.username)
    for u in getattr(entity, "usernames", None) or []:
        if u.active and u.username not in handles:
            handles.append(u.username)

    pc = getattr(entity, "profile_color", None)
    header = pattern = None
    if pc is not None:
        if pc.color is not None:
            header = await _profile_gradient(client, pc, dark)
        if pc.background_emoji_id:
            pattern = await _emoji_pattern(client, pc.background_emoji_id)

    return {
        "name": " ".join(x for x in (entity.first_name, entity.last_name) if x) or "Deleted",
        "premium": bool(getattr(entity, "premium", False)),
        "verified": bool(entity.verified),
        "bot": bool(entity.bot),
        "contact": bool(getattr(entity, "contact", False)),
        "is_self": bool(getattr(entity, "is_self", False)),
        "status": "" if entity.bot else presence(entity.status, L),
        "handles": handles,
        "bio": fu.about or "",
        "photo": data_uri(await client.download_profile_photo(entity, file=bytes)),
        "header": header,
        "pattern": pattern,
        "music": await _music(client, input_user, fu),
        "birthday": fmt_birthday(getattr(fu, "birthday", None)),
        "location": (getattr(getattr(fu, "business_location", None), "address", None) or None),
        "gifts": await _gifts(client, input_user),
        "channel": await _personal_channel(client, fu, full),
        "fetched_at": datetime.now(WIB),
    }
