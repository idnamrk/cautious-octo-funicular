#!/usr/bin/python3

import json
import os
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.gog.com/en/"
STORED_IDS_FILE = Path(__file__).with_name("gog_giveaway_sent_ids.txt")

bot_token = "your_bot_token_here"
chat_id = "target_chat_id_here"
message_thread_id = "target_message_thread_id_here"  # Optional: Set this if you want to send messages in a specific thread


class GiveawayParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.giveaway_depth = None
        self.header_depth = None
        self.found_section = False
        self.url = ""
        self.title = ""
        self.image_candidates = []
        self.in_header = False
        self.header_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.div_depth += 1
        classes = attrs.get("class", "").split()

        if tag == "div" and attrs.get("id") == "giveaway":
            self.giveaway_depth = self.div_depth
            self.found_section = True

        if self.giveaway_depth is None:
            return

        if tag == "a" and "giveaway__overlay-link" in classes:
            self.url = attrs.get("href", "")

        if tag == "div" and "giveaway__content-header" in classes:
            self.in_header = True
            self.header_depth = self.div_depth

        if tag == "img":
            alt = attrs.get("alt", "").strip()
            if alt.lower().endswith(" giveaway"):
                self.title = alt[:-len(" giveaway")]
            src = attrs.get("src", "")
            if src and "_giveaway_" in src:
                self.image_candidates.append(src)

        if tag == "source":
            for part in attrs.get("srcset", "").split(","):
                image_url = part.strip().split(" ")[0]
                if "_giveaway_" in image_url:
                    self.image_candidates.append(image_url)

    def handle_data(self, data):
        if self.in_header:
            self.header_parts.append(data)

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self.in_header and self.div_depth == self.header_depth:
            self.in_header = False
            self.header_depth = None
        if self.giveaway_depth is not None and self.div_depth == self.giveaway_depth:
            self.giveaway_depth = None
        self.div_depth = max(0, self.div_depth - 1)

    def result(self):
        if not self.found_section:
            return None
        if not self.url:
            # A giveaway section with no game URL is incomplete; do not change state.
            raise ValueError("Giveaway section exists but game link is missing")

        link = urllib.parse.urljoin(URL, self.url)
        parsed = urllib.parse.urlparse(link)
        if parsed.scheme != "https" or parsed.hostname != "www.gog.com":
            raise ValueError(f"Unexpected game URL: {link}")

        # Telegram sendPhoto reliably accepts JPEG URLs. Prefer larger 943x418 image.
        photos = [u for u in self.image_candidates if u.lower().split("?")[0].endswith(".jpg")]
        photos.sort(key=lambda u: (
            "_943x418" in u,
            "_2x.jpg" in u,
            "_465w" in u,
        ), reverse=True)
        if not photos:
            raise ValueError("Giveaway found, but no JPEG image URL was found")

        title = self.title.strip()
        if not title:
            header = " ".join(" ".join(self.header_parts).split())
            title = header.removeprefix("Giveaway:").split(" and don't miss", 1)[0].strip()
        if not title:
            title = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]).replace("_", " ")

        return {"id": link, "title": title, "url": link, "image": photos[0]}


def get_giveaway():
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = GiveawayParser()
    parser.feed(page)
    return parser.result()


def load_sent_ids():
    if not STORED_IDS_FILE.exists():
        return set()
    return {line.strip() for line in STORED_IDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}


def save_sent_ids(sent_ids):
    temp = STORED_IDS_FILE.with_suffix(".tmp")
    temp.write_text("".join(f"{item}\n" for item in sorted(sent_ids)), encoding="utf-8")
    temp.replace(STORED_IDS_FILE)


def send_telegram(giveaway):
    caption = f"🎁 GOG Giveaway!\n\n{giveaway['title']}\n{giveaway['url']}"
    payload = {
        "chat_id": chat_id,
        "photo": giveaway["image"],
        "caption": caption,
    }
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id

    data = urllib.parse.urlencode(payload).encode("utf-8")
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    req = urllib.request.Request(endpoint, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        answer = json.load(response)
    if not answer.get("ok"):
        raise RuntimeError(f"Telegram rejected sendPhoto: {answer}")


def main():
    giveaway = get_giveaway()  # On network/parser failure, do not overwrite the saved state.
    if giveaway is None:
        print("No active giveaway found")
        # Forget prior active giveaway so a later recurrence also triggers an alert.
        save_sent_ids(set())
        return

    sent_ids = load_sent_ids()
    if giveaway["id"] in sent_ids:
        print(f"Already notified: {giveaway['title']}")
        return

    send_telegram(giveaway)
    save_sent_ids({giveaway["id"]})
    print(f"Telegram photo sent: {giveaway['title']} - {giveaway['image']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
