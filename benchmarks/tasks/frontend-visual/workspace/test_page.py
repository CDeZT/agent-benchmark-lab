from html.parser import HTMLParser
from pathlib import Path


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.h1_text = ""
        self.status_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.current = "h1"
        elif attrs.get("id") == "status":
            self.current = "status"

    def handle_endtag(self, tag):
        self.current = None

    def handle_data(self, data):
        if self.current == "h1":
            self.h1_text += data.strip()
        elif self.current == "status":
            self.status_text += data.strip()


html = Path("index.html").read_text(encoding="utf-8")
parser = PageParser()
parser.feed(html)

assert parser.h1_text
assert parser.status_text == "PASS"
assert "TODO" not in html
