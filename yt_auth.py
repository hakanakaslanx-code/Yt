import os
import json
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# OAuth2 scope - sadece YouTube upload yetkisi
SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube.readonly']

_base_dir = os.environ.get('APP_BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.environ.get('CLIENT_SECRETS_FILE', os.path.join(_base_dir, 'client_secrets.json'))
TOKEN_FILE = os.environ.get('TOKEN_FILE', os.path.join(_base_dir, 'token.pickle'))
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/callback/youtube')

def get_auth_url():
    """OAuth2 login URL'si oluşturur."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return auth_url, state, flow

def exchange_code(code, state):
    """Auth kodunu token ile değiştirir ve kaydeder."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials
    # Token'ı kaydet
    with open(TOKEN_FILE, 'wb') as f:
        pickle.dump(credentials, f)
    return credentials

def get_youtube_service():
    """Kaydedilmiş token ile YouTube servisi oluşturur."""
    if not os.path.exists(TOKEN_FILE):
        return None, "Hesap bağlı değil"
    
    with open(TOKEN_FILE, 'rb') as f:
        credentials = pickle.load(f)
    
    # Süresi dolmuşsa yenile
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(credentials, f)
    
    service = build('youtube', 'v3', credentials=credentials)
    return service, None

def get_channel_info():
    """Bağlı kanalın bilgilerini çeker."""
    service, err = get_youtube_service()
    if err:
        return None, err
    
    request = service.channels().list(part='snippet,statistics', mine=True)
    response = request.execute()
    
    if response.get('items'):
        channel = response['items'][0]
        return {
            'id': channel['id'],
            'name': channel['snippet']['title'],
            'subs': channel['statistics'].get('subscriberCount', '0'),
            'videos': channel['statistics'].get('videoCount', '0'),
            'thumbnail': channel['snippet']['thumbnails']['default']['url']
        }, None
    return None, "Kanal bulunamadı"

def is_connected():
    """YouTube hesabı bağlı mı kontrol eder."""
    return os.path.exists(TOKEN_FILE)
