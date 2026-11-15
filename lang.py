"""Teks label UI + pengambilan language pack (t.me/setlanguage/xxx).

PENTING: nama key iOS di LANG_KEYS adalah tebakan terbaik. Jalankan
`python dump_lang.py <kode_bahasa>` untuk melihat key asli lalu sesuaikan.
Hanya key yang ada di LANG_KEYS yang bisa diganti (whitelist), panjang dibatasi.
"""
from telethon.tl.functions.langpack import GetLangPackRequest
from telethon.tl import types

DEFAULTS = {
    "call": "call",
    "video": "video",
    "mute": "mute",
    "search": "search",
    "more": "more",
    "username": "username",
    "bio": "bio",
    "also": "also",
    "channel": "CHANNEL",
    "subscribers": "subscribers",
    "online": "online",
    "recently": "last seen recently",
    "lastweek": "last seen within a week",
    "lastmonth": "last seen within a month",
    "longago": "last seen a long time ago",
    "lastseen": "last seen",
    "add_contact": "Add to Contacts",
    "block": "Block User",
}

# key_kita -> daftar kandidat key di language pack iOS
LANG_KEYS = {
    "call": ["PeerInfo.ButtonCall"],
    "video": ["PeerInfo.ButtonVideo"],
    "mute": ["PeerInfo.ButtonMute"],
    "search": ["PeerInfo.ButtonSearch"],
    "more": ["PeerInfo.ButtonMore"],
    "username": ["Profile.Username"],
    "bio": ["Profile.About"],
    "online": ["Presence.online"],
    "recently": ["Presence.recently"],
    "lastweek": ["Presence.lastWeek"],
    "lastmonth": ["Presence.lastMonth"],
    "longago": ["Presence.longTimeAgo"],
    "add_contact": ["PeerInfo.ButtonAddContact", "Profile.AddToContacts"],
    "block": ["Profile.BlockUser", "UserInfo.BlockUser"],
}

MAX_LEN = 40


async def fetch_pack(client, code: str) -> dict:
    pack = await client(GetLangPackRequest(lang_pack="ios", lang_code=code))
    out = {}
    for s in pack.strings:
        if isinstance(s, types.LangPackString):
            out[s.key] = s.value
        elif isinstance(s, types.LangPackStringPluralized):
            out[s.key] = s.other_value or s.one_value or ""
    return out


def clean(text: str) -> str:
    text = " ".join(text.split())  # buang newline/spasi ganda
    return text[:MAX_LEN]


async def load_strings(client, code: str | None) -> tuple[dict, bool]:
    """Balikin (strings, dipakai_custom)."""
    strings = dict(DEFAULTS)
    if not code:
        return strings, False
    pack = await fetch_pack(client, code)
    changed = False
    for ours, candidates in LANG_KEYS.items():
        for k in candidates:
            if k in pack and pack[k].strip():
                strings[ours] = clean(pack[k])
                changed = True
                break
    return strings, changed
