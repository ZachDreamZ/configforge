import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    svg_path = Path(r"D:\workspace\configforge\assets\architecture.svg")
    out_path = Path(r"D:\workspace\configforge\assets\architecture.png")
    
    svg = svg_path.read_text(encoding="utf-8")
    html = f"""<!DOCTYPE html><html><head><style>
body{{margin:0;background:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh}}
svg{{max-width:100%;height:auto}}
</style></head><body>{svg}</body></html>"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_path), full_page=True)
        await browser.close()
    print(f"Saved {out_path}")

asyncio.run(main())
