import os
import time
import random
import datetime
import json
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from yt_auth import get_youtube_service

# ── YouTube Quota Tracking ─────────────────────────────────────────────────────
# YouTube Data API v3 daily quota: 10,000 units
# video.insert  = 1,600 units
# thumbnails.set = 50 units
# playlistItems.insert = 50 units
# playlists.insert = 50 units
# liveBroadcasts.* = 50 units each

_QUOTA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quota.json')
_QUOTA_LIMIT = 10_000

_UNIT_COSTS = {
    'video.insert':             1600,
    'thumbnails.set':             50,
    'playlistItems.insert':       50,
    'playlists.insert':           50,
    'liveBroadcasts.insert':      50,
    'liveBroadcasts.update':      50,
    'liveStreams.insert':          50,
    'liveBroadcasts.list':        1,
    'liveStreams.list':            1,
}

def _quota_today_key():
    return datetime.date.today().isoformat()

def get_quota_usage():
    """Returns {used, limit, remaining, date} dict."""
    try:
        if os.path.exists(_QUOTA_FILE):
            with open(_QUOTA_FILE) as f:
                data = json.load(f)
            today = _quota_today_key()
            if data.get('date') == today:
                used = data.get('used', 0)
                return {"used": used, "limit": _QUOTA_LIMIT, "remaining": max(0, _QUOTA_LIMIT - used), "date": today}
    except Exception:
        pass
    return {"used": 0, "limit": _QUOTA_LIMIT, "remaining": _QUOTA_LIMIT, "date": _quota_today_key()}

def _track_quota(operation: str, count: int = 1):
    """Record quota usage for an API operation."""
    cost = _UNIT_COSTS.get(operation, 1) * count
    try:
        today = _quota_today_key()
        data  = {}
        if os.path.exists(_QUOTA_FILE):
            try:
                with open(_QUOTA_FILE) as f:
                    data = json.load(f)
            except Exception:
                pass
        if data.get('date') != today:
            data = {'date': today, 'used': 0, 'ops': {}}
        data['used'] = data.get('used', 0) + cost
        ops = data.setdefault('ops', {})
        ops[operation] = ops.get(operation, 0) + count
        with open(_QUOTA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    return cost

def check_quota_available(units_needed: int = 1600) -> bool:
    """Returns False if quota would be exceeded by this operation."""
    q = get_quota_usage()
    return (q['used'] + units_needed) <= _QUOTA_LIMIT


# ── Exponential Backoff Helper ─────────────────────────────────────────────────
def _api_call_with_retry(fn, max_retries=4, initial_wait=2):
    """
    Calls fn() with exponential backoff on transient HTTP errors.
    Retries on 429 (quota), 500, 503. Raises immediately on 400/401/403/404.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except HttpError as e:
            status = e.resp.status
            if status in (400, 401, 403, 404):
                raise   # Non-retryable
            last_exc = e
            if attempt < max_retries:
                wait = initial_wait * (2 ** attempt) + random.uniform(0, 1)
                print(f"[API] HTTP {status} — retry {attempt+1}/{max_retries} in {wait:.1f}s")
                time.sleep(wait)
        except Exception as e:
            raise   # Non-HTTP errors: don't retry
    raise last_exc

_PLAYLIST_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')

def _load_playlist_cache():
    if os.path.exists(_PLAYLIST_CACHE_FILE):
        try:
            with open(_PLAYLIST_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_playlist_cache(data):
    with open(_PLAYLIST_CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_or_create_playlist(genre, channel_slug=None):
    """
    Genre/vibe'a göre playlist adı türetir.
    Yoksa oluşturur, varsa ID'sini döner. Cache'ler.
    """
    service, err = get_youtube_service(channel_slug)
    if err:
        return None

    # Playlist adı: genre'dan ilk 2 kelime + "Mix | Allone AI"
    words      = genre.strip().split()
    pl_name    = ' '.join(w.capitalize() for w in words[:3]) + " Mix | Allone AI"
    cache_key  = (channel_slug or 'default') + '::' + pl_name
    cache      = _load_playlist_cache()

    if cache_key in cache:
        print(f"[Playlist] Mevcut: {pl_name} ({cache[cache_key]})")
        return cache[cache_key]

    try:
        # Yeni playlist oluştur
        resp = service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": pl_name,
                    "description": f"Auto-generated AI music playlist — {genre}\nPowered by Allone AI",
                    "defaultLanguage": "en"
                },
                "status": {"privacyStatus": "public"}
            }
        ).execute()
        pl_id = resp["id"]
        cache[cache_key] = pl_id
        _save_playlist_cache(cache)
        print(f"[Playlist] Oluşturuldu: {pl_name} → {pl_id}")
        return pl_id
    except Exception as e:
        print(f"[Playlist] Hata: {e}")
        return None

def add_video_to_playlist(video_id, playlist_id, channel_slug=None):
    """Videoyu playlist'e ekler."""
    service, err = get_youtube_service(channel_slug)
    if err:
        return False
    try:
        _api_call_with_retry(lambda: service.playlistItems().insert(
            part="snippet",
            body={"snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}
            }}
        ).execute())
        _track_quota('playlistItems.insert')
        print(f"[Playlist] Video eklendi: {video_id} → {playlist_id}")
        return True
    except Exception as e:
        print(f"[Playlist] Video ekleme hatası: {e}")
        return False


def set_thumbnail(video_id, image_path, channel_slug=None):
    """Yüklenen videonun thumbnail'ini AI ile üretilen görsel olarak ayarlar."""
    if not image_path or not os.path.exists(image_path):
        print(f"Thumbnail: dosya bulunamadı ({image_path})")
        return False
    service, err = get_youtube_service(channel_slug)
    if err:
        print(f"Thumbnail: YouTube bağlantısı yok — {err}")
        return False
    try:
        _api_call_with_retry(lambda: service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(image_path, mimetype='image/jpeg')
        ).execute())
        _track_quota('thumbnails.set')
        print(f"Thumbnail ayarlandi: {video_id}")
        return True
    except Exception as e:
        print(f"Thumbnail hatasi: {e}")
        return False


def upload_video(video_path, title, description, tags=None, privacy='private', channel_slug=None):
    # Quota check before upload (1600 units per video.insert)
    if not check_quota_available(1600):
        q = get_quota_usage()
        print(f"[Uploader] QUOTA LIMIT — {q['used']}/{q['limit']} units used today. Upload skipped.")
        return None

    service, err = get_youtube_service(channel_slug)
    if err:
        print(f"HATA: YouTube bağlantısı yok - {err}")
        return None

    if not os.path.exists(video_path):
        print(f"HATA: Video dosyası bulunamadı: {video_path}")
        return None

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or ['AI Music', 'Lofi', 'Chill'],
            'categoryId': '10'
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=1024 * 1024 * 5
    )

    print(f"YouTube'a yükleniyor: {title}")
    req = service.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    # Resumable upload with per-chunk retry on transient errors
    response = None
    retries  = 0
    MAX_CHUNK_RETRIES = 5
    while response is None:
        try:
            status, response = req.next_chunk()
            if status:
                print(f"  Yükleme: {int(status.progress() * 100)}%")
            retries = 0  # reset on success
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                retries += 1
                if retries > MAX_CHUNK_RETRIES:
                    print(f"[Uploader] Max chunk retries exceeded.")
                    raise
                wait = 2 ** retries + random.uniform(0, 1)
                print(f"[Uploader] HTTP {e.resp.status} — chunk retry {retries}/{MAX_CHUNK_RETRIES} in {wait:.1f}s")
                time.sleep(wait)
            else:
                raise

    _track_quota('video.insert')
    video_id = response.get('id') if response else None
    if not video_id:
        print(f"[Uploader] HATA: YouTube response'ta video ID yok: {response}")
        return None
    q = get_quota_usage()
    print(f"Yuklendi: https://youtube.com/watch?v={video_id}  [Quota: {q['used']}/{q['limit']}]")
    return video_id


# ── Keyword / Vibe Haritaları ──────────────────────────────────────────────

_MOOD_MAP = {
    'dark':       ('🌑', 'Dark', ['dark music', 'dark ambient', 'dark vibes']),
    'sad':        ('😢', 'Sad',  ['sad music', 'emotional', 'melancholy']),
    'happy':      ('☀️', 'Happy', ['happy music', 'feel good', 'uplifting']),
    'epic':       ('⚡', 'Epic', ['epic music', 'powerful', 'cinematic epic']),
    'calm':       ('🌊', 'Calm', ['calm music', 'peaceful', 'relaxing']),
    'chill':      ('❄️', 'Chill', ['chill music', 'chill beats', 'lofi chill']),
    'lofi':       ('🎧', 'Lofi', ['lofi beats', 'lofi hip hop', 'lofi music']),
    'rain':       ('🌧️', 'Rainy', ['rain sounds', 'rainy day music', 'rain ambience']),
    'night':      ('🌙', 'Night', ['night music', 'late night vibes', 'midnight']),
    'city':       ('🏙️', 'Urban', ['city vibes', 'urban music', 'city sounds']),
    'cyberpunk':  ('🤖', 'Cyberpunk', ['cyberpunk music', 'synthwave', 'neon lights']),
    'fantasy':    ('🧙', 'Fantasy', ['fantasy music', 'magical', 'epic fantasy']),
    'anime':      ('⛩️', 'Anime', ['anime music', 'japanese aesthetic', 'anime lofi']),
    'study':      ('📚', 'Study', ['study music', 'focus music', 'concentration']),
    'sleep':      ('💤', 'Sleep', ['sleep music', 'relaxing sleep', 'deep sleep']),
    'meditation': ('🧘', 'Meditation', ['meditation music', 'zen', 'mindfulness']),
    'jazz':       ('🎷', 'Jazz', ['jazz music', 'smooth jazz', 'jazz beats']),
    'piano':      ('🎹', 'Piano', ['piano music', 'piano beats', 'soft piano']),
    'forest':     ('🌲', 'Forest', ['forest sounds', 'nature music', 'woodland']),
    'space':      ('🚀', 'Space', ['space music', 'cosmic', 'ambient space']),
}

_STYLE_MAP = {
    'Cinematic':   ['cinematic music', 'film score', 'orchestral'],
    'Anime':       ['anime ost', 'anime beats', 'japanese music'],
    'Cyberpunk':   ['cyberpunk', 'synthwave', 'retrowave', 'darksynth'],
    'Realistic':   ['realistic', 'organic music', 'natural'],
    'Digital Art': ['digital music', 'electronic', 'digital art music'],
}

_TITLE_TEMPLATES = [
    "{emoji} {mood} {style} Mix | {use} Music {year} | No Copyright",
    "{emoji} {prompt_title} | {style} Beats | Study & Chill {year}",
    "{emoji} {mood} {style} | {use} & Focus Music | No Copyright",
    "{emoji} {prompt_title} Vibes | {style} Mix {year} | No Copyright",
    "{emoji} Best {mood} {style} Music | {use} Playlist {year}",
    "{emoji} {prompt_title} | Chill {style} Beats | No Copyright {year}",
    "{emoji} {mood} {style} Atmosphere | {use} Music {year}",
    "{emoji} {prompt_title} | Deep {style} Mix | No Copyright Music",
]

_USE_CASES = [
    'Study', 'Work', 'Focus', 'Relax', 'Sleep', 'Coding',
    'Reading', 'Gaming', 'Meditation', 'Lofi'
]

_HASHTAG_BASE = [
    '#lofi', '#chillmusic', '#studymusic', '#nocopyrightmusic',
    '#aimusic', '#relaxingmusic', '#focusmusic', '#freemusicforvideos',
    '#royaltyfreemusic', '#chillbeats', '#workmusic', '#backgroundmusic'
]


def _extract_keywords(prompt):
    """Prompttan anahtar kelimeleri çıkarır."""
    prompt_lower = prompt.lower()
    found_moods = []
    found_emojis = []
    found_extra_tags = []

    for word, (emoji, label, tags) in _MOOD_MAP.items():
        if word in prompt_lower:
            found_moods.append(label)
            found_emojis.append(emoji)
            found_extra_tags.extend(tags)

    # Prompt'tan temiz başlık oluştur
    words = prompt.strip().split()
    title_words = [w.capitalize() for w in words[:5]]
    prompt_title = ' '.join(title_words)

    return found_moods, found_emojis, found_extra_tags, prompt_title


def generate_seo_metadata(genre, style, image_url=None, music_prompt=None):
    """
    Prompt ve stile göre SEO optimize başlık, açıklama ve etiket üretir.
    music_prompt verilirse title keyword'leri oradan çekilir (title-müzik uyumu).
    Her çağrıda farklı kombinasyon oluşturur.
    """
    year = datetime.datetime.now().year
    # Keyword extraction: önce music_prompt, yoksa genre kullan
    moods, emojis, extra_tags, prompt_title = _extract_keywords(music_prompt or genre)

    # Emoji seç
    emoji = emojis[0] if emojis else random.choice(['🎵', '🎶', '🎧', '🎼', '✨', '🌙', '⚡'])

    # Mood etiketi
    mood = moods[0] if moods else style

    # Use case seç
    use = random.choice(_USE_CASES)

    # Başlık şablonu seç
    template = random.choice(_TITLE_TEMPLATES)
    title = template.format(
        emoji=emoji,
        mood=mood,
        style=style,
        use=use,
        year=year,
        prompt_title=prompt_title
    )
    # Max 100 karakter (YouTube limiti)
    title = title[:100]

    # Stil etiketleri
    style_tags = _STYLE_MAP.get(style, [style.lower()])

    # Genre-aware base tags — lofi sabit değil, genre'a göre seçilir
    g_lower = genre.lower()
    if any(k in g_lower for k in ['lofi', 'lo-fi', 'hip hop', 'chillhop']):
        base_tags = ['lofi', 'lofi hip hop', 'chill beats', 'lofi music', 'study beats']
    elif any(k in g_lower for k in ['jazz', 'saxophone', 'bebop']):
        base_tags = ['jazz music', 'smooth jazz', 'jazz beats', 'instrumental jazz']
    elif any(k in g_lower for k in ['80s', 'synthwave', 'retro', 'vhs']):
        base_tags = ['80s music', 'synthwave', 'retrowave', 'retro music', 'neon']
    elif any(k in g_lower for k in ['cyberpunk', 'cyber', 'darksynth']):
        base_tags = ['cyberpunk music', 'dark synthwave', 'electronic', 'futuristic music']
    elif any(k in g_lower for k in ['classical', 'piano', 'orchestra']):
        base_tags = ['classical music', 'piano music', 'instrumental', 'neoclassical']
    elif any(k in g_lower for k in ['ambient', 'meditation', 'zen', 'nature']):
        base_tags = ['ambient music', 'meditation music', 'relaxing', 'zen music']
    elif any(k in g_lower for k in ['house', 'afro', 'deep']):
        base_tags = ['deep house', 'afro house', 'electronic music', 'house music']
    else:
        base_tags = ['chill music', 'instrumental', 'background music']

    # Tüm etiketler
    prompt_words = [w.lower() for w in genre.split() if len(w) > 3]
    all_tags = list(set(
        prompt_words +
        extra_tags +
        style_tags +
        base_tags +
        ['AI music', 'no copyright', 'royalty free', 'focus music',
         mood.lower(), style.lower(), use.lower()]
    ))[:30]  # YouTube max 30 etiket

    # Hashtag'ler
    mood_hashtags = [f'#{m.lower().replace(" ", "")}' for m in moods[:3]]
    style_hashtag = f'#{style.lower()}'
    hashtags = ' '.join(list(set(_HASHTAG_BASE[:6] + mood_hashtags + [style_hashtag])))

    # Görsel satırı
    image_line = f"Cover Art: {image_url}" if image_url else "Cover Art: AI Generated (Flux 1.1 Pro)"

    # Açıklama
    description = f"""{emoji} {prompt_title} — {style} Mix | No Copyright Music

🔔 Subscribe for daily AI music uploads → https://www.youtube.com/@AloneAI
{image_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎵 About This Track
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Genre: {genre}
Style: {style}
Perfect for: {use}, focus, relaxation, and background listening

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Free To Use — No Copyright
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This music is 100% copyright-free. Use it in:
  • YouTube videos & Shorts
  • Twitch streams & podcasts
  • Study / work / gaming sessions
  • Social media (Instagram, TikTok, etc.)

Credit not required, but appreciated!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👍 Like this track? Drop a comment below!
🔔 New music every day — hit Subscribe!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{hashtags}
"""

    return title, description, all_tags


def update_live_broadcast_title(new_title: str, channel_slug=None):
    """Aktif YouTube canlı yayının başlığını değiştirir."""
    service, err = get_youtube_service(channel_slug)
    if err:
        return False, f"YouTube bağlantısı yok: {err}"
    try:
        resp = service.liveBroadcasts().list(
            part="id,snippet",
            broadcastStatus="active",
            maxResults=5
        ).execute()
        items = resp.get('items', [])
        if not items:
            resp2 = service.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="all",
                maxResults=10
            ).execute()
            items = [i for i in resp2.get('items', [])
                     if i.get('snippet', {}).get('liveBroadcastContent') in ('live', 'upcoming')]
        if not items:
            return False, "Aktif yayın bulunamadı"
        broadcast = items[0]
        old_snippet = broadcast.get('snippet', {})
        # YouTube API: update'e sadece yazılabilir alanlar gönderilmeli
        # Read-only alanlar (liveBroadcastContent, actualStartTime, vb.) 400 hatası verir
        clean_snippet = {
            'title':              new_title[:100],
            'description':        old_snippet.get('description', ''),
            'scheduledStartTime': old_snippet.get('scheduledStartTime', ''),
        }
        service.liveBroadcasts().update(
            part="snippet",
            body={"id": broadcast['id'], "snippet": clean_snippet}
        ).execute()
        return True, f"Başlık güncellendi: {new_title[:50]}"
    except Exception as e:
        return False, str(e)


def get_or_create_live_stream_key(title="AI Music 24/7 Live Stream", channel_slug=None):
    """
    YouTube API üzerinden stream key'i otomatik alır, yoksa yeni oluşturur.
    Returns: (stream_key, broadcast_id, error_message)
    """
    from datetime import datetime, timezone, timedelta
    service, err = get_youtube_service(channel_slug)
    if err:
        return None, None, f"YouTube bağlantısı yok: {err}"
    try:
        # 1. Mevcut liveStream'leri listele
        resp = service.liveStreams().list(
            part="snippet,cdn,status", mine=True, maxResults=10
        ).execute()
        items = resp.get('items', [])
        stream_id  = None
        stream_key = None

        for item in items:
            s = item.get('status', {}).get('streamStatus', '')
            if s in ('ready', 'active', 'inactive', ''):
                ingestion  = item['cdn']['ingestionInfo']
                stream_key = ingestion.get('streamName')
                stream_id  = item['id']
                break

        # 2. Stream yoksa yeni oluştur
        if not stream_key:
            ns = service.liveStreams().insert(
                part="snippet,cdn",
                body={
                    "snippet": {"title": title},
                    "cdn": {
                        "frameRate": "30fps",
                        "ingestionType": "rtmp",
                        "resolution": "1080p"
                    }
                }
            ).execute()
            stream_key = ns['cdn']['ingestionInfo'].get('streamName')
            stream_id  = ns['id']

        # 3. Upcoming broadcast var mı — bind et
        broadcast_id = None
        try:
            br = service.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="upcoming",
                maxResults=5
            ).execute()
            upcoming = br.get('items', [])
            if upcoming:
                broadcast_id = upcoming[0]['id']
            else:
                # Yeni broadcast oluştur
                start_time = (datetime.now(timezone.utc) + timedelta(minutes=2)
                              ).strftime('%Y-%m-%dT%H:%M:%S.000Z')
                nb = service.liveBroadcasts().insert(
                    part="snippet,status,contentDetails",
                    body={
                        "snippet": {
                            "title": title,
                            "scheduledStartTime": start_time,
                        },
                        "status": {"privacyStatus": "public"},
                        "contentDetails": {
                            "enableAutoStart": True,
                            "enableAutoStop":  False,
                            "latencyPreference": "normal",
                            "enableDvr": True,
                        }
                    }
                ).execute()
                broadcast_id = nb['id']
            # Bind stream → broadcast
            if broadcast_id and stream_id:
                service.liveBroadcasts().bind(
                    part="id,contentDetails",
                    id=broadcast_id,
                    streamId=stream_id
                ).execute()
        except Exception as be:
            print(f"[LiveStream] Broadcast bind hatası (önemsiz): {be}")

        return stream_key, broadcast_id, None

    except Exception as e:
        return None, None, str(e)
