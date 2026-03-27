import os
import requests


def send_notification(message: str, retries: int = 2) -> bool:
    """Telegram bot üzerinden bildirim gönderir. Başarısız olursa retry yapar."""
    import time as _time
    token   = os.getenv('TELEGRAM_TOKEN', '').strip()
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for attempt in range(retries):
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            if resp.ok:
                return True
            print(f"[Telegram] HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[Telegram] Deneme {attempt+1}/{retries} basarisiz: {e}")
        if attempt < retries - 1:
            _time.sleep(2 ** attempt)  # 1s, 2s backoff
    return False


def notify_uploaded(title: str, yt_url: str, genre: str):
    send_notification(
        f"✅ <b>Video Yüklendi!</b>\n\n"
        f"🎵 <b>{title}</b>\n"
        f"🎭 Vibe: {genre}\n"
        f"🔗 <a href='{yt_url}'>{yt_url}</a>"
    )


def notify_error(genre: str, error: str):
    send_notification(
        f"❌ <b>Hata!</b>\n\n"
        f"🎭 Vibe: {genre}\n"
        f"💬 {error}"
    )


def notify_shorts_uploaded(title: str, yt_url: str):
    send_notification(
        f"📱 <b>Shorts Yüklendi!</b>\n\n"
        f"🎵 {title}\n"
        f"🔗 <a href='{yt_url}'>{yt_url}</a>"
    )


def notify_weekly_report(total_videos: int, uploaded: int, genres: list):
    top_genres = ', '.join(genres[:3]) if genres else '—'
    send_notification(
        f"📊 <b>Haftalık Rapor</b>\n\n"
        f"🎬 Üretilen Video: <b>{total_videos}</b>\n"
        f"📤 YouTube'a Yüklenen: <b>{uploaded}</b>\n"
        f"🎵 En Çok: {top_genres}\n\n"
        f"🤖 Allone AI — Otomatik Rapor"
    )
