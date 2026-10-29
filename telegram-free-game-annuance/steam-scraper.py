#!/usr/bin/python3

import json
import html
import os
import re
import ssl
import urllib.request
from urllib.parse import quote

URL = "https://store.steampowered.com/search/results/?force_infinite=1&maxprice=free&specials=1&l=english&json=1"
STORED_IDS_FILE = os.path.join(os.path.dirname(__file__), "steam_sent_ids.txt")


def normalize_required_age(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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

    ratings = payload.get("ratings", {}) if isinstance(payload.get("ratings", {}), dict) else {}
    steam_germany = ratings.get("steam_germany", {}) if isinstance(ratings, dict) else {}
    global_required_age = normalize_required_age(payload.get("required_age", 0))
    steam_germany_required_age = normalize_required_age(steam_germany.get("required_age", 0))

    return {
        "type": payload.get("type", ""),
        "header_image": payload.get("header_image", ""),
        "required_age": global_required_age,
        "steam_germany_required_age": steam_germany_required_age,
        "price_overview": payload.get("price_overview", {}),
    }


def get_items() -> list[dict] | None:
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
            return None

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

# DEBUG: Uncomment the following function to use mock data for testing purposes
# def mock_get_items() -> list[dict]:
#     return [
#         {
#             "name": "Sample Game 1",
#             "id": "123456",
#             "link": "https://store.steampowered.com/app/123456/",
#         }
#     ]


def enrich_items(items: list[dict]) -> list[dict]:
    for item in items:
        item_id = item.get("id", "")
        item["metadata"] = fetch_app_metadata(item_id)
        item["image"] = item["metadata"].get("header_image", "")
        item["type"] = item["metadata"].get("type", "")
        item["required_age"] = item["metadata"].get("required_age", 0)
        item["steam_germany_required_age"] = item["metadata"].get("steam_germany_required_age", 0)
        item["price_overview"] = item["metadata"].get("price_overview", {})

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


def html_escape(text: str) -> str:
    return html.escape(html.unescape(text), quote=False)


def filter_new_items(items: list[dict], sent_ids: set[str]) -> list[dict]:
    return [item for item in items if str(item.get("id", "")) and str(item.get("id", "")) not in sent_ids]


def cleanup_sent_ids(items: list[dict], sent_ids: set[str]) -> set[str]:
    current_ids = {str(item.get("id", "")) for item in items if str(item.get("id", ""))}
    return {item_id for item_id in sent_ids if item_id in current_ids}


if __name__ == "__main__":
    items = get_items()
    if items is None:
        print("Fetch failed; aborting without changing sent IDs.")
        raise SystemExit(1)

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
    message_thread_id = "target_message_thread_id_here"  # Optional: Set this if you want to send messages in a specific thread

    for item in items:
        image_url = item.get("image", "") or "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/4165910/6e3f2fedcd1e7faa80fe3b5c349a62a73dde5d10/header.jpg"

        item_type = str(item.get("type", "")).strip()
        if item_type and item_type.lower() != "game":
            title_prefix = f"[{item_type.upper()}] "
        else:
            title_prefix = ""

        price_overview = item.get("price_overview") or {}
        initial_price = str(price_overview.get("initial_formatted", "")).strip()
        final_price = str(price_overview.get("final_formatted", "")).strip()

        if initial_price and final_price and initial_price != final_price:
            price_line = f"<s>{html_escape(initial_price)}</s> -> {html_escape(final_price)}"
        elif final_price:
            price_line = html_escape(final_price)
        else:
            price_line = ""

        required_ages = [
            item.get("required_age", 0),
            item.get("steam_germany_required_age", 0),
        ]
        spoiler_enabled = any(normalize_required_age(age) >= 18 for age in required_ages)

        caption = f"{html_escape(title_prefix)}{html_escape(item.get('name', ''))}\n{html_escape(item.get('link', ''))}"
        if price_line:
            caption = f"{caption}\n{price_line}"
        escaped_caption = quote(caption, safe="")
        escaped_image = quote(image_url, safe="")
        photo_url = (
            f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            f"?chat_id={chat_id}&photo={escaped_image}&caption={escaped_caption}&parse_mode=HTML"
        )
        if spoiler_enabled:
            photo_url += "&has_spoiler=true"
        if message_thread_id:
            photo_url += f"&message_thread_id={message_thread_id}"
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
