"""
YouTube Analytics + API Kredi Takibi
"""
import os
import requests
from datetime import datetime, timedelta

try:
    from yt_auth import get_youtube_service, load_channels
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False


# ── YouTube Analytics ─────────────────────────────────────────────────────────

def get_channel_analytics(slug=None, days=28):
    """Son N günün görüntülenme, watch time, abone kazanımını döner."""
    if not HAS_AUTH:
        return None
    try:
        from googleapiclient.discovery import build
        from yt_auth import get_youtube_service
        service, err = get_youtube_service(slug)
        if err:
            return None

        end_date   = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Channel ID bul
        ch_resp = service.channels().list(part='id', mine=True).execute()
        if not ch_resp.get('items'):
            return None
        channel_id = ch_resp['items'][0]['id']

        # YouTube Analytics API için ayrı servis
        # Credentials nesnesini service'den güvenli şekilde çek
        _creds = None
        try:
            _creds = service._http.credentials
        except AttributeError:
            try:
                _creds = service._credentials
            except AttributeError:
                pass
        if _creds is None:
            return None
        analytics = build('youtubeAnalytics', 'v2', credentials=_creds)
        report = analytics.reports().query(
            ids=f'channel=={channel_id}',
            startDate=start_date,
            endDate=end_date,
            metrics='views,estimatedMinutesWatched,subscribersGained,subscribersLost',
            dimensions='day',
            sort='day'
        ).execute()

        rows = report.get('rows', [])
        if not rows:
            return {"views": 0, "watch_hours": 0, "subs_gained": 0, "subs_net": 0, "chart": [], "days": days}
        total_views    = sum(r[1] for r in rows if len(r) > 1)
        total_wt_min   = sum(r[2] for r in rows if len(r) > 2)
        subs_gained    = sum(r[3] for r in rows if len(r) > 3)
        subs_lost      = sum(r[4] for r in rows if len(r) > 4)

        # Son 7 gün için daily chart data
        last7 = rows[-7:] if len(rows) >= 7 else rows
        chart = [{"date": r[0], "views": r[1]} for r in last7]

        return {
            "views":        int(total_views),
            "watch_hours":  round(total_wt_min / 60, 1),
            "subs_gained":  int(subs_gained),
            "subs_net":     int(subs_gained - subs_lost),
            "chart":        chart,
            "days":         days,
        }
    except Exception as e:
        print(f"[Analytics] {e}")
        return None


def get_all_channels_analytics():
    """Tüm bağlı kanalların analytics özetini döner."""
    if not HAS_AUTH:
        return []
    channels = load_channels()
    results = []
    for ch in channels:
        data = get_channel_analytics(ch['slug'])
        results.append({
            "channel": ch,
            "analytics": data,
        })
    return results


# ── API Kredi Takibi ──────────────────────────────────────────────────────────

def get_replicate_credits():
    """Replicate hesap bakiyesini döner."""
    token = os.getenv('REPLICATE_API_TOKEN', '')
    if not token:
        return None
    try:
        resp = requests.get(
            'https://api.replicate.com/v1/account',
            headers={'Authorization': f'Token {token}'},
            timeout=10
        )
        if resp.ok:
            data = resp.json()
            return {
                "username": data.get('username', ''),
                "type":     data.get('type', ''),
            }
    except Exception as e:
        print(f"[Replicate] {e}")
    return None


def get_kie_credits():
    """KIE.ai kredi bakiyesini döner."""
    key = os.getenv('KIE_API_KEY', '')
    if not key:
        return None
    try:
        resp = requests.get(
            'https://api.kie.ai/api/v1/account',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            timeout=10
        )
        if resp.ok:
            data = resp.json()
            d = data.get('data', data)
            return {
                "credits":  d.get('credits') or d.get('balance') or d.get('quota') or '?',
                "plan":     d.get('plan') or d.get('membership') or '?',
            }
    except Exception as e:
        print(f"[KIE] {e}")
    return None


def get_api_status():
    """Tüm API durumlarını tek seferde döner."""
    return {
        "replicate": get_replicate_credits(),
        "kie":       get_kie_credits(),
    }


# ── Trending Konu Takibi ──────────────────────────────────────────────────────

_TRENDING_SEARCHES = [
    # YouTube trending music queries - manual curated list + RSS fallback
    "lofi hip hop beats",
    "dark ambient music",
    "cyberpunk synthwave",
    "jazz beats study",
    "meditation music",
    "lo-fi chill beats",
    "epic cinematic music",
    "rain sounds ambient",
    "anime lofi mix",
    "sleep music relaxing",
]

def get_trending_music_topics(limit=8):
    """
    YouTube Music / RSS trending başlıklarını döner.
    Önce YouTube Data API, yoksa curated list.
    """
    topics = []

    # YouTube trending via Data API
    try:
        if HAS_AUTH:
            from yt_auth import get_youtube_service
            service, err = get_youtube_service()
            if not err:
                resp = service.videos().list(
                    part='snippet',
                    chart='mostPopular',
                    videoCategoryId='10',   # Music category
                    maxResults=limit,
                    regionCode='US'
                ).execute()
                for item in resp.get('items', []):
                    snip = item['snippet']
                    topics.append({
                        "title":     snip.get('title', ''),
                        "channel":   snip.get('channelTitle', ''),
                        "tags":      snip.get('tags', [])[:5],
                        "source":    "youtube_trending",
                    })
    except Exception as e:
        print(f"[Trending] YouTube API: {e}")

    # Fallback: curated + RSS
    if not topics:
        try:
            # YouTube Music trending RSS
            resp = requests.get(
                "https://www.youtube.com/feeds/videos.xml?playlist_id=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI",
                timeout=8
            )
            if resp.ok:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry in root.findall('atom:entry', ns)[:limit]:
                    title_el = entry.find('atom:title', ns)
                    if title_el is not None:
                        topics.append({
                            "title":  title_el.text or '',
                            "source": "rss",
                        })
        except Exception:
            pass

    if not topics:
        topics = [{"title": t, "source": "curated"} for t in _TRENDING_SEARCHES[:limit]]

    return topics[:limit]
