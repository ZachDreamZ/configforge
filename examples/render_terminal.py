import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    html_path = Path(r"D:\workspace\configforge\hyperframes\terminal.html").resolve()
    out_path = Path(r"D:\workspace\configforge\hyperframes\terminal-preview.png")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(f"file:///{html_path.as_posix()}", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        term = page.locator(".term")
        box = await term.bounding_box()
        await page.screenshot(path=str(out_path), clip={"x": box["x"]-40, "y": box["y"]-40, "width": box["width"]+80, "height": box["height"]+80})
        await browser.close()
    print(f"Saved {out_path}")

asyncio.run(main())
