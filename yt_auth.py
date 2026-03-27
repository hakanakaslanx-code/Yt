import os
import json
import pickle
import shutil
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
]

_base_dir           = os.environ.get('APP_BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.environ.get('CLIENT_SECRETS_FILE', os.path.join(_base_dir, 'client_secrets.json'))
TOKEN_FILE          = os.environ.get('TOKEN_FILE',          os.path.join(_base_dir, 'token.pickle'))
REDIRECT_URI        = os.environ.get('REDIRECT_URI',        'http://localhost:5000/callback/youtube')
CHANNELS_FILE       = os.path.join(_base_dir, 'channels.json')


# ── Channel Registry ──────────────────────────────────────────────────────────

def _token_path(slug: str) -> str:
    return os.path.join(_base_dir, f'token_{slug}.pickle')


def load_channels() -> list:
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    # Migrate legacy token.pickle → channels.json
    if os.path.exists(TOKEN_FILE):
        try:
            ch = _fetch_channel_from_token(TOKEN_FILE)
            if ch:
                slug = ch['id']
                shutil.copy(TOKEN_FILE, _token_path(slug))
                ch['is_default'] = True
                _save_channels([ch])
                return [ch]
        except Exception:
            pass
    return []


def _save_channels(channels: list):
    with open(CHANNELS_FILE, 'w') as f:
        json.dump(channels, f, indent=2)


def get_default_channel() -> dict | None:
    channels = load_channels()
    return next((c for c in channels if c.get('is_default')), channels[0] if channels else None)


def set_default_channel(slug: str):
    channels = load_channels()
    for c in channels:
        c['is_default'] = (c['slug'] == slug)
    _save_channels(channels)


def remove_channel(slug: str):
    channels = load_channels()
    ch = next((c for c in channels if c['slug'] == slug), None)
    if ch:
        tp = _token_path(slug)
        if os.path.exists(tp):
            os.remove(tp)
        channels = [c for c in channels if c['slug'] != slug]
        if ch.get('is_default') and channels:
            channels[0]['is_default'] = True
        _save_channels(channels)
    return ch


def _fetch_channel_from_token(token_file: str) -> dict | None:
    try:
        with open(token_file, 'rb') as f:
            credentials = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, Exception) as e:
        print(f"[Auth] Token dosyası okunamadı ({token_file}): {e}")
        return None
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            with open(token_file, 'wb') as f:
                pickle.dump(credentials, f)
        except Exception as e:
            print(f"[Auth] Token yenileme hatası ({token_file}): {e}")
            return None
    service = build('youtube', 'v3', credentials=credentials)
    resp = service.channels().list(part='snippet,statistics', mine=True).execute()
    if not resp.get('items'):
        return None
    item = resp['items'][0]
    thumbs = item['snippet'].get('thumbnails', {})
    thumb_url = (thumbs.get('default') or thumbs.get('medium') or thumbs.get('high') or {}).get('url', '')
    return {
        'id':        item['id'],
        'slug':      item['id'],
        'name':      item['snippet']['title'],
        'subs':      item['statistics'].get('subscriberCount', '0'),
        'videos':    item['statistics'].get('videoCount', '0'),
        'thumbnail': thumb_url,
        'is_default': False,
    }


def register_channel_from_token(token_file: str) -> dict | None:
    """Yeni auth'dan gelen token dosyasını alıp channels.json'a ekler."""
    try:
        ch = _fetch_channel_from_token(token_file)
        if not ch:
            return None
        slug = ch['id']
        dest = _token_path(slug)
        shutil.copy(token_file, dest)
        channels = load_channels()
        existing = next((c for c in channels if c['id'] == slug), None)
        if existing:
            existing.update(ch)
            existing['is_default'] = existing.get('is_default', False)
        else:
            ch['is_default'] = not bool(channels)   # İlk kanal → default
            channels.append(ch)
        _save_channels(channels)
        return ch
    except Exception as e:
        print(f"[yt_auth] register_channel_from_token error: {e}")
        return None


# ── OAuth Flow ────────────────────────────────────────────────────────────────

def get_auth_url():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    return auth_url, state, flow


def exchange_code(code, state):
    """Auth kodunu token ile değiştirir → geçici token.pickle'a yazar, register_channel_from_token çağrılır."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials
    with open(TOKEN_FILE, 'wb') as f:
        pickle.dump(credentials, f)
    # Hemen channels.json'a kaydet
    register_channel_from_token(TOKEN_FILE)
    return credentials


# ── YouTube Service ───────────────────────────────────────────────────────────

def get_youtube_service(slug: str = None):
    """slug verilirse o kanalın token'ını, yoksa default kanalınkini kullanır."""
    if slug:
        token_file = _token_path(slug)
    else:
        default = get_default_channel()
        token_file = _token_path(default['slug']) if default else TOKEN_FILE

    if not os.path.exists(token_file):
        return None, "Token dosyası bulunamadı"

    try:
        with open(token_file, 'rb') as f:
            credentials = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, Exception) as e:
        print(f"[Auth] Token dosyası bozuk ({token_file}): {e}")
        return None, f"Token dosyası bozuk: {e}"

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            with open(token_file, 'wb') as f:
                pickle.dump(credentials, f)
        except Exception as e:
            print(f"[Auth] Token yenileme hatası: {e}")
            return None, f"Token süresi dolmuş ve yenilenemedi: {e}"

    return build('youtube', 'v3', credentials=credentials), None


def get_channel_info(slug: str = None):
    service, err = get_youtube_service(slug)
    if err:
        return None, err
    resp = service.channels().list(part='snippet,statistics', mine=True).execute()
    if resp.get('items'):
        item = resp['items'][0]
        thumbs = item['snippet'].get('thumbnails', {})
        thumb_url = (thumbs.get('default') or thumbs.get('medium') or thumbs.get('high') or {}).get('url', '')
        return {
            'id':        item['id'],
            'name':      item['snippet']['title'],
            'subs':      item['statistics'].get('subscriberCount', '0'),
            'videos':    item['statistics'].get('videoCount', '0'),
            'thumbnail': thumb_url,
        }, None
    return None, "Kanal bulunamadı"


def is_connected(slug: str = None) -> bool:
    if slug:
        return os.path.exists(_token_path(slug))
    channels = load_channels()
    if channels:
        return True
    return os.path.exists(TOKEN_FILE)
