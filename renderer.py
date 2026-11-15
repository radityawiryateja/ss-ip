import os
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from playwright.async_api import async_playwright

BASE = Path(__file__).parent
env = Environment(loader=FileSystemLoader(BASE / "templates"),
                  autoescape=select_autoescape(["html"]))


def linkify(text: str) -> Markup:
    safe = str(escape(text))
    safe = re.sub(r"(@\w{4,32})", r'<span class="lnk">\1</span>', safe)
    safe = re.sub(r"(https?://[^\s<]+)", r'<span class="lnk">\1</span>', safe)
    return Markup(safe.replace("\n", "<br>"))


env.filters["linkify"] = linkify

# posisi emoji pattern di sekeliling avatar (x, y, rotasi)
PATTERN_POS = [(24, 70, -15), (70, 112, 10), (28, 158, 8), (100, 70, 18),
               (112, 160, -12), (60, 196, -8), (300, 72, 12), (340, 118, -10),
               (278, 156, 14), (346, 176, -14), (250, 68, -18), (306, 198, 8),
               (150, 54, 5), (230, 54, -5)]


class Renderer:
    async def start(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(args=["--no-sandbox"])

    async def stop(self):
        await self.browser.close()
        await self.pw.stop()

    async def render(self, profile: dict, theme: dict, strings: dict,
                     full: bool, mark: str) -> bytes:
        html = env.get_template("profile.html").render(
            p=profile, t=theme, L=strings, full=full, mark=mark,
            clock=profile["fetched_at"].strftime("%H.%M"),
            battery=os.getenv("BATTERY", "").strip(),
            pattern_pos=PATTERN_POS,
        )
        page = await self.browser.new_page(
            viewport={"width": 430, "height": 1400},
            device_scale_factor=3 if full else 2,
        )
        try:
            await page.set_content(html, wait_until="load")
            card = await page.query_selector("#card")
            return await card.screenshot(type="png", omit_background=True)
        finally:
            await page.close()
