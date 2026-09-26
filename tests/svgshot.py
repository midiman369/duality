import sys, re, pathlib, base64
from playwright.sync_api import sync_playwright
pairs = list(zip(sys.argv[1::2], sys.argv[2::2]))
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    for svg, png in pairs:
        txt = pathlib.Path(svg).read_text()
        w, h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', txt).groups())
        pg = b.new_page(viewport={'width': int(w) + 20, 'height': int(h) + 20})
        pg.set_content(f'<html><body style="margin:0;background:#fff"><img id="i" src="data:image/svg+xml;base64,{base64.b64encode(txt.encode()).decode()}" width="{w}" height="{h}"></body></html>')
        pg.wait_for_timeout(300)
        pg.screenshot(path=png, clip={'x': 0, 'y': 0, 'width': w, 'height': h})
        pg.close()
    b.close()
