import os
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
TO_EMAILS = os.environ.get("TO_EMAILS")
to_emails = [email.strip() for email in TO_EMAILS.split(",")]

DIVAR_URL = "https://api.divar.ir/v8/postlist/w/search"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Basic eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaWQiOiI5MTk4OWY5MS0xZDE3LTQzNzEtODI5NS04NTJhMjlkYTU3OWUiLCJ1aWQiOiI4OWU4ZjI2ZC03ZTI1LTQwZmEtYWVmZC0wY2FhMmYwZjBmNzQiLCJ1c2VyIjoiMDkzNzk0NTUwODgiLCJ2ZXJpZmllZF90aW1lIjoxNzUzMTg5ODE2LCJpc3MiOiJhdXRoIiwidXNlci10eXBlIjoicGVyc29uYWwiLCJ1c2VyLXR5cGUtZmEiOiLZvtmG2YQg2LTYrti124wiLCJleHAiOjE3NTU3ODE4MTYsImlhdCI6MTc1MzE4OTgxNn0.TFyOnW61H3uVZN6LgMkKb4jUQm3tTtUTh_ZKrP_71Q4",
    "User-Agent": "Mozilla/5.0",
}

SEEN_FILE = "seen_ads.json"

FILTER_KEYWORDS = ["همخونه", "هم‌خونه"]


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)


def contains_filter_keyword(text):
    if not text:
        return False
    text_lower = text.lower()
    for kw in FILTER_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def fetch_ads():
    try:
        with open("body.json", encoding="utf-8") as f:
            body = json.load(f)
    except Exception as e:
        print(f"❌ خطا در خواندن فایل body.json: {e}")
        return []

    try:
        response = requests.post(DIVAR_URL, headers=HEADERS, json=body)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در درخواست به API دیوار: {e}")
        return []

    try:
        data = response.json()
    except Exception as e:
        print(f"❌ خطا در تجزیه JSON پاسخ API: {e}")
        return []

    ads = []

    widgets = data.get("list_widgets", [])
    for widget in widgets:
        if widget.get("widget_type") == "POST_ROW":
            post_data = widget.get("data", {})
            action = post_data.get("action", {})
            payload = action.get("payload", {})
            token = payload.get("token")
            title = post_data.get("title", "")
            description = payload.get("description", "")
            web_info = payload.get("web_info", {})
            district = web_info.get("district_persian", "")
            city = web_info.get("city_persian", "")
            image_url = post_data.get("image_url", "")
            deposit = post_data.get("top_description_text", "")
            rent = post_data.get("middle_description_text", "")

            if contains_filter_keyword(title) or contains_filter_keyword(description):
                continue

            if token and title:
                ads.append(
                    {
                        "id": token,
                        "title": title,
                        "district": district,
                        "city": city,
                        "image_url": image_url,
                        "deposit": deposit,
                        "rent": rent,
                        "url": f"https://divar.ir/v/{token}",
                    }
                )

    print(f"Extracted {len(ads)} ads from posts (after filtering)")
    return ads


def send_email(new_ads):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"🏠 آگهی‌های جدید دیوار - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    msg["From"] = SMTP_USERNAME
    msg["To"] = TO_EMAILS

    text_content = "\n\n".join(
        [
            f"{ad['title']} - {ad['district']} - {ad['city']}\nودیعه: {ad['deposit']}\nاجاره: {ad['rent']}\n{ad['url']}"
            for ad in new_ads
        ]
    )

    html_content = "<h2>آگهی‌های جدید دیوار:</h2><ul>"
    for ad in new_ads:
        html_content += f"""
        <li style="margin-bottom:20px;">
            <a href="{ad['url']}" target="_blank" style="text-decoration:none; color:#333;">
                <img src="{ad['image_url']}" alt="تصویر آگهی" style="width:120px; height:auto; vertical-align:middle; border-radius:5px; margin-left:10px;">
                <strong>{ad['title']}</strong><br>
                {ad['district']} - {ad['city']}<br>
                <span style="color: #d9534f; font-weight: bold;">ودیعه: {ad['deposit']}</span><br>
                <span style="color: #5cb85c; font-weight: bold;">اجاره: {ad['rent']}</span>
            </a>
        </li>
        """
    html_content += "</ul>"

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")

    msg.attach(part1)
    msg.attach(part2)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, to_emails, msg.as_string())
        print("📧 ایمیل با موفقیت ارسال شد.")
    except Exception as e:
        print(f"❌ خطا در ارسال ایمیل: {e}")


def main():
    seen = load_seen()
    ads = fetch_ads()
    new_ads = [ad for ad in ads if ad["id"] not in seen]

    if new_ads:
        print(f"✅ {len(new_ads)} آگهی جدید پیدا شد")
        send_email(new_ads)
        seen.update(ad["id"] for ad in new_ads)
        save_seen(seen)
    else:
        print("❌ آگهی جدیدی نیست")
        save_seen(seen)


if __name__ == "__main__":
    main()
