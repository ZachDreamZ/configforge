import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    svg_path = Path(r"D:\workspace\configforge\assets\architecture.svg")
    out_path = Path(r"D:\workspace\configforge\assets\architecture.png")
    
    svg_content = svg_path.read_text(encoding="utf-8")
    html = f"""<!DOCTYPE html>
<html><head><style>body{{margin:0;background:#fff;}}</style></head>
<body>{svg_content}</body></html>"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 700})
        await page.set_content(html)
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(out_path), full_page=True)
        await browser.close()
    print(f"Saved to {out_path}")

asyncio.run(main())
