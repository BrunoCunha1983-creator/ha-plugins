from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .utils import BASE_URL, DEFAULT_KEYWORDS, compact_text, parse_pt_number


def tag_text(tag: Tag | None) -> str | None:
    return compact_text(tag.get_text(" ", strip=True)) if tag else None


def order_status_from_steps(steps: list[dict[str, Any]], fallback: str | None) -> str | None:
    for step in steps:
        classes = set(step.get("classes", []))
        if classes.intersection({"picking", "shipping", "delivery", "delivering"}):
            return step.get("description") or fallback
    filled = [step for step in steps if "filled" in set(step.get("classes", []))]
    if filled:
        return filled[-1].get("description") or fallback
    return fallback


def parse_orders_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    current_orders: list[dict[str, Any]] = []

    for card in soup.select(".current-card"):
        number = compact_text(card.get("data-order-nb"))
        order_name = tag_text(card.select_one(".order-name"))
        if not number and order_name:
            match = re.search(r"(\d{5,})", order_name)
            number = match.group(1) if match else None

        delivery_window = tag_text(card.select_one(".formatted-date"))
        if delivery_window:
            delivery_window = delivery_window.strip("()")
        fallback_status = tag_text(card.select_one(".order-date.order"))

        steps: list[dict[str, Any]] = []
        step_elements = card.select(".order-progress .progress-step")
        for index, step in enumerate(step_elements):
            description = tag_text(step.select_one(".step-description"))
            day = tag_text(step.select_one(".step-day"))
            time = tag_text(step.select_one(".step-time"))
            steps.append(
                {
                    "index": index + 1,
                    "description": description,
                    "day": day,
                    "time": time,
                    "classes": list(step.get("class", [])),
                }
            )

        completed = sum(1 for step in steps if "filled" in set(step["classes"]))
        active_index = next(
            (
                step["index"]
                for step in steps
                if set(step["classes"]).intersection(
                    {"picking", "shipping", "delivery", "delivering"}
                )
            ),
            completed,
        )
        progress = round((max(completed, active_index) / len(steps)) * 100) if steps else None
        map_node = card.select_one(".google-maps-container")
        detail_link = card.select_one(".order-detail-link a")
        final_description = steps[-1].get("description") if steps else None
        address = None
        if final_description and final_description.lower().startswith("entregue na "):
            address = final_description[12:].strip()

        current_orders.append(
            {
                "number": number,
                "name": order_name,
                "status": order_status_from_steps(steps, fallback_status),
                "summary_status": fallback_status,
                "delivery_window": delivery_window,
                "progress": progress,
                "steps": steps,
                "address": address,
                "postal_code": map_node.get("data-postal-code") if map_node else None,
                "detail_url": urljoin(BASE_URL, detail_link.get("href"))
                if detail_link and detail_link.get("href")
                else None,
            }
        )

    history: list[dict[str, Any]] = []
    for card in soup.select(".order-card"):
        title = tag_text(card.select_one(".order-title")) or tag_text(card.select_one(".order-name"))
        number = None
        if title:
            match = re.search(r"(\d{5,})", title)
            number = match.group(1) if match else None
        status_date = tag_text(card.select_one(".order-date"))
        detail_link = card.select_one(".order-detail-link a")
        history.append(
            {
                "number": number,
                "status_date": status_date,
                "total": parse_pt_number(card.get("data-store-total")),
                "saving": parse_pt_number(card.get("data-store-saving")),
                "store": compact_text(card.get("data-store-name")),
                "in_store": str(card.get("data-in-store", "false")).lower() == "true",
                "detail_url": urljoin(BASE_URL, detail_link.get("href"))
                if detail_link and detail_link.get("href")
                else None,
            }
        )

    page_text = compact_text(soup.get_text(" ", strip=True)) or ""
    detected_words = sorted({word for word in DEFAULT_KEYWORDS if word.lower() in page_text.lower()})
    digest_payload = json.dumps(
        {"current_orders": current_orders, "history": history[:20]},
        ensure_ascii=False,
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()

    return {
        "current_orders": current_orders,
        "active_orders": len(current_orders),
        "current_order": current_orders[0] if current_orders else None,
        "history": history,
        "purchase_history_count": len(history),
        "last_order": history[0] if history else None,
        "detected_words": detected_words,
        "fingerprint": fingerprint,
    }


def parse_coupons_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Tag] = []
    seen: set[int] = set()
    selectors = (
        ".coupon-card",
        ".coupon-item",
        "[data-coupon-id]",
        "[data-coupon-code]",
        "[data-promotion-id]",
    )
    for selector in selectors:
        for tag in soup.select(selector):
            if id(tag) in seen or tag.find_parent(id="coupon-modal"):
                continue
            seen.add(id(tag))
            candidates.append(tag)

    coupons: list[dict[str, Any]] = []
    for tag in candidates:
        title = tag_text(
            tag.select_one(
                ".coupon-title, .product-title, .title, [data-coupon-title]"
            )
        )
        description = tag_text(tag.select_one(".coupon-description, .description"))
        expiry = tag_text(
            tag.select_one(
                ".coupon-expiration-date, .expiration-date, .expiry-date, .validity"
            )
        )
        raw_text = tag_text(tag)
        if not any((title, description, expiry)) and not raw_text:
            continue
        classes = set(tag.get("class", []))
        coupons.append(
            {
                "id": tag.get("data-coupon-id")
                or tag.get("data-coupon-code")
                or tag.get("data-promotion-id"),
                "title": title or raw_text,
                "description": description,
                "expiry": expiry,
                "active": bool(classes.intersection({"active", "activated", "selected"}))
                or str(tag.get("data-active", "false")).lower() == "true",
            }
        )

    return {
        "coupons": coupons,
        "coupon_count": len(coupons) if candidates else None,
        "active_coupon_count": sum(1 for coupon in coupons if coupon["active"])
        if candidates
        else None,
    }
