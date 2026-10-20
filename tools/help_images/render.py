"""Рисунки справки: HTML/SVG → PNG (Chromium). python tools/help_images/render.py"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
HERE = Path(__file__).parent
OUT = HERE.parent.parent / "services" / "help" / "app" / "content" / "images"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(device_scale_factor=2)
        for f in sorted(HERE.glob("*.html")):
            await pg.goto(f.as_uri())
            await (await pg.query_selector("svg")).screenshot(path=str(OUT / f"{f.stem}.png"))
            print(f.stem)
        await b.close()
asyncio.run(main())
