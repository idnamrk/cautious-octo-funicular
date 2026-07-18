#!/usr/bin/python3

import json
import os
import ssl
import urllib.request
from urllib.parse import quote

# test link for debugging
# URL = "https://catalog.gog.com/v1/catalog?limit=1&price=between:0,0&order=desc:trending&countryCode=HU&currencyCode=HUF&page=8"
URL = "https://catalog.gog.com/v1/catalog?limit=48&price=between:0,0&order=desc:trending&discounted=eq:true&countryCode=HU&currencyCode=HUF&page=1"
STORED_IDS_FILE = os.path.join(os.path.dirname(__file__), "gog_sent_ids.txt")


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


def get_products() -> list[dict]:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except Exception:
        try:
            unverified_context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=20, context=unverified_context) as response:
                data = json.load(response)
        except Exception:
            return []

    products = data.get("products")
    if not isinstance(products, list):
        return []

    return products


def filter_new_products(products: list[dict], sent_ids: set[str]) -> list[dict]:
    return [product for product in products if str(product.get("id", "")) and str(product.get("id", "")) not in sent_ids]


def cleanup_sent_ids(products: list[dict], sent_ids: set[str]) -> set[str]:
    current_ids = {str(product.get("id", "")) for product in products if str(product.get("id", ""))}
    return {item_id for item_id in sent_ids if item_id in current_ids}


if __name__ == "__main__":
    products = get_products()
    sent_ids = load_sent_ids()
    sent_ids = cleanup_sent_ids(products, sent_ids)

    new_products = filter_new_products(products, sent_ids)

    bot_token = "your_bot_token_here"
    chat_id = "target_chat_id_here"
    message_thread_id = "target_message_thread_id_here"  # Optional: Set this if you want to send messages in a specific thread

    for product in new_products:
        product_id = str(product.get("id", ""))
        title = product.get("title", "")
        store_link = product.get("storeLink", "")
        image_url = product.get("coverHorizontal", "") or product.get("logo", "") or "https://www.gog.com/favicon.ico"

        caption = f"{title}\n{store_link}" if title or store_link else ""
        escaped_caption = quote(caption, safe="")
        escaped_image = quote(image_url, safe="")
        photo_url = (
            f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            f"?chat_id={chat_id}&photo={escaped_image}&caption={escaped_caption}"
        )
        if message_thread_id:
            photo_url += f"&message_thread_id={message_thread_id}"

        try:
            with urllib.request.urlopen(photo_url, timeout=20) as response:
                sent_ids.add(product_id)
                print(f"Sent GOG image: {image_url}")
        except Exception:
            try:
                unverified_context = ssl._create_unverified_context()
                with urllib.request.urlopen(photo_url, timeout=20, context=unverified_context) as response:
                    sent_ids.add(product_id)
                    print(f"Sent GOG image: {image_url}")
            except Exception as exc:
                print(f"Failed to send GOG image {image_url}: {exc}")

    save_sent_ids(sent_ids)

