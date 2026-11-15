"""Preset tema + pengambilan tema custom (t.me/addtheme/xxx, khusus iOS)."""
import re

from telethon.tl.functions.account import GetThemeRequest
from telethon.tl.types import InputThemeSlug

PRESETS = {
    "dark": dict(dark=True, bg="#000000", card="#1c1c1e", text="#ffffff",
                 sub="#8e8e93", accent="#3e88f7", sep="#38383a", btn="#1c1c1e"),
    "light": dict(dark=False, bg="#f2f2f7", card="#ffffff", text="#000000",
                  sub="#8a8a8e", accent="#007aff", sep="#e5e5ea", btn="#ffffff"),
    "pink": dict(dark=False, bg="#fdf0f5", card="#ffffff", text="#1f1418",
                 sub="#a07888", accent="#e0559a", sep="#f3d9e4", btn="#ffffff"),
    "dark pink": dict(dark=True, bg="#180c13", card="#2a1620", text="#ffeef5",
                      sub="#b58a9d", accent="#ff6fa8", sep="#4a2a3a", btn="#2a1620"),
    "dark blue": dict(dark=True, bg="#050a1a", card="#0f1a33", text="#eaf1ff",
                      sub="#7f93bb", accent="#4da3ff", sep="#1f3052", btn="#0f1a33"),
}


def hex_from_int(c: int) -> str:
    return f"#{c & 0xFFFFFF:06x}"


def _parse_color(value: str):
    """Terima 'ffffff', '#ffffff', 'ffffffff' (RGBA). Balikin '#rrggbb' atau None."""
    v = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", v):
        return "#" + v[:6].lower()
    return None


# key di file .tgios-theme -> variabel tema kita
TGIOS_KEYS = {
    "list.blocksBackgroundColor": "bg",
    "list.itemBlocksBackgroundColor": "card",
    "list.itemPrimaryTextColor": "text",
    "list.itemSecondaryTextColor": "sub",
    "list.itemAccentColor": "accent",
    "list.itemBlocksSeparatorColor": "sep",
}


def parse_tgios(raw: bytes) -> dict:
    out = {}
    for line in raw.decode("utf-8", "ignore").splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        if k in TGIOS_KEYS:
            c = _parse_color(v)
            if c:
                out[TGIOS_KEYS[k]] = c
    return out


async def load_custom_theme(client, slug: str) -> dict:
    """Balikin override warna. Kalau gagal / bukan tema iOS -> {}."""
    theme = await client(GetThemeRequest(format="ios", theme=InputThemeSlug(slug=slug)))
    over = {}

    # 1) Warna dasar dari settings (tema berbasis accent)
    for s in getattr(theme, "settings", None) or []:
        base = type(s.base_theme).__name__.lower()
        over["dark"] = any(x in base for x in ("night", "tinted"))
        if getattr(s, "accent_color", None) is not None:
            over["accent"] = hex_from_int(s.accent_color)
        break

    # 2) Kalau ada file .tgios-theme, timpa dengan warna lengkapnya
    doc = getattr(theme, "document", None)
    if doc is not None:
        try:
            raw = await client.download_media(doc, file=bytes)
            over.update(parse_tgios(raw))
        except Exception:
            pass
    return over


def build_theme(preset: str, override: dict | None) -> dict:
    over = override or {}
    base = dict(PRESETS[preset])
    # tema custom tanpa preset eksplisit: pilih dasar gelap/terang sesuai tema
    if override and preset == "dark" and over.get("dark") is False:
        base = dict(PRESETS["light"])
    base.update({k: v for k, v in over.items() if v is not None})
    return base
