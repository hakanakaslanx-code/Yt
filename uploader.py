import os
import time
from googleapiclient.http import MediaFileUpload
from yt_auth import get_youtube_service

def upload_video(video_path, title, description, tags=None, privacy='private'):
    """
    Videoyu YouTube'a yükler.
    
    Args:
        video_path: MP4 dosyasının yolu
        title: Video başlığı (SEO için otomatik oluşturulabilir)
        description: Video açıklaması
        tags: Etiket listesi
        privacy: 'public', 'private', veya 'unlisted'
    
    Returns:
        video_id (str): Yüklenen videonun YouTube ID'si
    """
    service, err = get_youtube_service()
    if err:
        print(f"HATA: YouTube bağlantısı yok - {err}")
        return None
    
    if not os.path.exists(video_path):
        print(f"HATA: Video dosyası bulunamadı: {video_path}")
        return None
    
    # Video metadata
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or ['AI Music', 'Lofi', 'Chill', 'Automation', 'Allone'],
            'categoryId': '10'  # Müzik kategorisi
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }
    
    # Dosyayı yükle (resumable upload ile)
    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=1024*1024*5  # 5MB chunk
    )
    
    print(f"YouTube'a yükleniyor: {title}")
    print(f"Durum: {privacy} | Dosya: {os.path.basename(video_path)}")
    
    request = service.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"  Yükleme İlerlemesi: {progress}%")
    
    video_id = response.get('id')
    print(f"✅ Video başarıyla yüklendi!")
    print(f"   YouTube URL: https://youtube.com/watch?v={video_id}")
    return video_id

def generate_seo_metadata(genre, style):
    """Müzik türüne göre SEO dostu başlık ve açıklama oluşturur."""
    title = f"{genre} {style} Mix 🎵 | AI Generated Chill Music | No Copyright"
    description = f"""🎵 {genre} {style} Mix - Completely AI Generated Music
    
🤖 Created with Allone AI Music Automation
🎨 Visuals: AI Generated Artwork
🎵 Music: AI Composed & Produced

✅ No Copyright - Free to use for:
• YouTube videos
• Twitch streams  
• Podcasts & content creation

🔔 Subscribe for daily AI music uploads!

Tags: {genre}, {style}, lofi beats, chill music, study music, work music, 
relaxing music, AI music, royalty free, no copyright music
"""
    tags = [genre, style, 'lofi', 'chill music', 'AI music', 'study music',
            'relaxing', 'no copyright', 'free music', 'automation']
    
    return title, description, tags
