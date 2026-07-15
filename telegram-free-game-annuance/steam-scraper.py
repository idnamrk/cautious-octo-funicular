#!/usr/bin/python3

import json
import os
import re
import ssl
import urllib.request
from urllib.parse import quote

URL = "https://store.steampowered.com/search/results/?force_infinite=1&maxprice=free&specials=1&l=english&json=1"
STORED_IDS_FILE = os.path.join(os.path.dirname(__file__), "steam_sent_ids.txt")


def extract_app_id(logo_link: str) -> str:
    if not logo_link:
        return ""

    match = re.search(r"http.*?apps/([^/]+)/", logo_link, re.DOTALL)
    return match.group(1) if match else ""


def fetch_app_metadata(app_id: str) -> dict:
    if not app_id:
        return {}

    details_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english&cc=hu"
    request = urllib.request.Request(details_url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except Exception:
        try:
            unverified_context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=20, context=unverified_context) as response:
                data = json.load(response)
        except Exception:
            return {}

    app_data = data.get(app_id, {}) if isinstance(data, dict) else {}
    if not isinstance(app_data, dict):
        return {}

    payload = app_data.get("data", {})
    if not isinstance(payload, dict):
        return {}

    return {
        "type": payload.get("type", ""),
        "header_image": payload.get("header_image", ""),
    }


def get_items() -> list[dict]:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            data = json.load(response)
    except Exception:
        try:
            unverified_context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=20, context=unverified_context) as response:
                data = json.load(response)
        except Exception:
            return []

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("The response did not contain an 'items' array.")

    parsed_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        item_id = extract_app_id(item.get("logo", ""))
        parsed_item = {
            "name": item.get("name", ""),
            "id": item_id,
            "link": f"https://store.steampowered.com/app/{item_id}/" if item_id else "",
        }
        parsed_items.append(parsed_item)

    return parsed_items


def enrich_items(items: list[dict]) -> list[dict]:
    for item in items:
        item_id = item.get("id", "")
        item["metadata"] = fetch_app_metadata(item_id)
        item["image"] = item["metadata"].get("header_image", "")
        item["type"] = item["metadata"].get("type", "")

    return items


def load_sent_ids() -> set[str]:
    if not os.path.exists(STORED_IDS_FILE):
        return set()

    try:
        with open(STORED_IDS_FILE, "r", encoding="utf-8") as handle:
            return {str(line.strip()) for line in handle if str(line).strip()}
    except Exception:
        return set()


def save_sent_ids(sent_ids: set[str]) -> None:
    with open(STORED_IDS_FILE, "w", encoding="utf-8") as handle:
        for item_id in sorted(sent_ids):
            if item_id:
                handle.write(f"{item_id}\n")


def filter_new_items(items: list[dict], sent_ids: set[str]) -> list[dict]:
    return [item for item in items if str(item.get("id", "")) and str(item.get("id", "")) not in sent_ids]


def cleanup_sent_ids(items: list[dict], sent_ids: set[str]) -> set[str]:
    current_ids = {str(item.get("id", "")) for item in items if str(item.get("id", ""))}
    return {item_id for item_id in sent_ids if item_id in current_ids}


if __name__ == "__main__":
    items = get_items()
    sent_ids = load_sent_ids()
    sent_ids = cleanup_sent_ids(items, sent_ids)

    new_items = filter_new_items(items, sent_ids)
    items = enrich_items(new_items)

    # DEBUG: Print the items in a tabular format
    # headers = ["name", "id", "link", "image"]
    # rows = []
    # for item in items:
    #     rows.append([item.get("name", ""), item.get("id", ""), item.get("link", ""), item.get("image", "")])

    # col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]

    # def format_row(row):
    #     return " | ".join(str(value).ljust(col_widths[i]) for i, value in enumerate(row))

    # print(format_row(headers))
    # print("-+-".join("-" * width for width in col_widths))
    # for row in rows:
    #     print(format_row(row))

    bot_token = "your_bot_token_here"
    chat_id = "target_chat_id_here"

    for item in items:
        image_url = item.get("image", "") or "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/4165910/6e3f2fedcd1e7faa80fe3b5c349a62a73dde5d10/header.jpg"

        caption = f"{item.get('name', '')}\n{item.get('link', '')}"
        escaped_caption = quote(caption, safe="")
        escaped_image = quote(image_url, safe="")
        photo_url = (
            f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            f"?chat_id={chat_id}&photo={escaped_image}&caption={escaped_caption}"
        )
        try:
            with urllib.request.urlopen(photo_url, timeout=20) as response:
                sent_ids.add(str(item.get("id", "")))
                print(f"Sent image: {image_url}")
        except Exception as exc:
            try:
                unverified_context = ssl._create_unverified_context()
                with urllib.request.urlopen(photo_url, timeout=20, context=unverified_context) as response:
                    sent_ids.add(str(item.get("id", "")))
                    print(f"Sent image: {image_url}")
            except Exception as fallback_exc:
                print(f"Failed to send image {image_url}: {fallback_exc}")

    save_sent_ids(sent_ids)
