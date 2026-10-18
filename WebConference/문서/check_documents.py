"""Check offline document links, SVGs, layout, and screenshots; no production access."""
import json
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "RelayServer" / "test-results" / "documentation"
PAGES = ["개발상세서.html", "화상회의_상세매뉴얼.html"]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "문서" / "diagrams").glob("*.svg"):
        ElementTree.parse(path)
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for page_index, filename in enumerate(PAGES):
            source = ROOT / filename
            parser = Links()
            parser.feed(source.read_text(encoding="utf-8"))
            assert len(parser.ids) == len(set(parser.ids)), "Duplicate IDs"
            for href in parser.links:
                if href.startswith("#"):
                    assert href[1:] in parser.ids, href
                elif not href.startswith(("https:", "http:")):
                    assert (source.parent / href).is_file(), href
            page = browser.new_page(viewport={"width":1440,"height":1000}, device_scale_factor=1)
            errors, external = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: external.append(request.url) if request.url.startswith(("http:","https:")) else None)
            page.goto(source.as_uri())
            page.evaluate("document.fonts.ready")
            assert page.locator("h1").count() == 1
            assert page.locator("h2").count() == (17 if page_index == 0 else 14)
            page.screenshot(path=str(OUTPUT / f"{page_index}-desktop.png"))
            headings = page.locator("main h2")
            for index in range(headings.count()):
                headings.nth(index).evaluate("el=>el.scrollIntoView({block:'start'})")
                page.screenshot(path=str(OUTPUT / f"{page_index}-section-{index+1:02}.png"))
            for index in range(page.locator("figure").count()):
                page.locator("figure").nth(index).screenshot(path=str(OUTPUT / f"{page_index}-diagram-{index+1}.png"))
            svg_overflow = page.evaluate("""() => [...document.querySelectorAll('svg')].flatMap(svg => {
                const box=svg.viewBox.baseVal;
                return [...svg.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x<0||b.y<0||b.x+b.width>box.width||b.y+b.height>box.height}).map(t=>t.textContent);
            })""")
            assert not svg_overflow, svg_overflow
            page.set_viewport_size({"width":390,"height":844})
            page.evaluate("document.querySelector('.contents details').open=false; window.scrollTo(0,0)")
            page.screenshot(path=str(OUTPUT / f"{page_index}-mobile.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflow"
            headings.nth(3).evaluate("el=>el.scrollIntoView({block:'start'})")
            page.screenshot(path=str(OUTPUT / f"{page_index}-mobile-content.png"))
            assert not errors, errors
            assert not external, external
            # Check print styling without adding an unrequested PDF deliverable.
            page.emulate_media(media="print")
            assert page.locator(".contents").is_hidden()
            report.append({"file":filename,"chapters":headings.count(),"diagrams":page.locator("svg").count(),"links":len(parser.links),"external_requests":len(external),"errors":errors})
            page.close()
        browser.close()
    (OUTPUT/"validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=True))


if __name__ == "__main__":
    main()
