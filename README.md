# YouTube Music Automation

Bu proje, Suno ve Flux AI kullanarak otomatik müzik videoları üretir ve YouTube'a yükler.

## Kurulum
1. Python yükleyin.
2. Gerekli kütüphaneleri kurun: `pip install -r requirements.txt`
3. `.env.example` dosyasının adını `.env` yapın ve API anahtarlarınızı girin.

## Modüller
- `music_gen.py`: Suno API (Kie.ai) ile müzik üretir.
- `image_gen.py`: Flux (Replicate) ile görsel üretir (Yakında).
- `video_engine.py`: Müzik ve görseli birleştirir (Yakında).
- `uploader.py`: YouTube'a yükleme yapar (Yakında).
