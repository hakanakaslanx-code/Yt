# MoviePy v2.x Uyumlu Video Motoru — Animated Overlay Edition
HAS_MOVIEPY = False
try:
    from moviepy import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip, VideoClip, VideoFileClip
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
    HAS_MOVIEPY = True
except ImportError:
    try:
        from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip, VideoClip, VideoFileClip
        from moviepy.audio.fx.audio_fadein import AudioFadeIn
        from moviepy.audio.fx.audio_fadeout import AudioFadeOut
        HAS_MOVIEPY = True
    except ImportError:
        print("[WARN] MoviePy bulunamadi — video render calismayacak. Kur: pip install moviepy")

import os
import numpy as np

# Ses analizi için librosa (opsiyonel)
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


# ── Efekt Tespiti ──────────────────────────────────────────────────────────────
def _detect_effect(text):
    """Genre/lyrics metnine göre hangi parçacık efektinin kullanılacağını belirler."""
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in ['rain', 'dark', 'sad', 'storm', 'melancholy', 'mellow', 'yagmur', 'karanlik']):
        return 'rain'
    if any(k in t for k in ['space', 'cosmic', 'galaxy', 'star', 'universe', 'nebula', 'aurora', 'uzay']):
        return 'stars'
    if any(k in t for k in ['cyberpunk', 'neon', 'cyber', 'glitch', 'synthwave', 'retrowave', 'vaporwave',
                             '80s', '80\'s', 'eighties', 'retro', 'cassette', 'vhs', 'arcade']):
        return 'cyberpunk'
    if any(k in t for k in ['forest', 'nature', 'leaf', 'woodland', 'autumn', 'fall', 'wind', 'orman']):
        return 'leaves'
    return None


# ── Yağmur Efekti ──────────────────────────────────────────────────────────────
def _make_rain_clip(w, h, duration):
    rng = np.random.default_rng(42)
    N = 200
    xs      = rng.integers(0, w, N)
    phases  = rng.uniform(0, h + 50, N)
    lengths = rng.integers(15, 50, N)
    speeds  = rng.uniform(300, 550, N)
    alphas  = rng.integers(110, 200, N)

    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        y_bases = ((phases + t * speeds) % (h + lengths) - lengths).astype(int)
        for i in range(N):
            x  = int(xs[i])
            y0 = max(0, y_bases[i])
            y1 = min(h, y_bases[i] + lengths[i])
            if y0 < y1 and 0 <= x < w:
                a = int(alphas[i])
                frame[y0:y1, x, 0] = a // 4   # R: hafif mavi tint
                frame[y0:y1, x, 1] = a // 3   # G
                frame[y0:y1, x, 2] = a         # B: baskın
        return frame

    return VideoClip(make_frame, duration=duration)


# ── Yıldız Efekti ──────────────────────────────────────────────────────────────
def _make_stars_clip(w, h, duration):
    rng = np.random.default_rng(7)
    N = 140
    xs     = rng.integers(0, w, N)
    ys     = rng.integers(0, h, N)
    freqs  = rng.uniform(0.4, 3.0, N)
    phases = rng.uniform(0, 2 * np.pi, N)
    sizes  = rng.integers(1, 3, N)

    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        brightnesses = (100 + 155 * np.abs(np.sin(t * freqs + phases))).astype(np.uint8)
        for i in range(N):
            b  = int(brightnesses[i])
            s  = int(sizes[i])
            y0, y1 = max(0, ys[i] - s), min(h, ys[i] + s + 1)
            x0, x1 = max(0, xs[i] - s), min(w, xs[i] + s + 1)
            frame[y0:y1, x0:x1, 0] = b
            frame[y0:y1, x0:x1, 1] = b
            frame[y0:y1, x0:x1, 2] = min(255, b + 50)  # biraz daha mavi/mor
        return frame

    return VideoClip(make_frame, duration=duration)


# ── Cyberpunk Glitch Efekti ─────────────────────────────────────────────────────
def _make_cyberpunk_clip(w, h, duration):
    rng = np.random.default_rng(13)
    scan_ys      = rng.integers(0, h, 10)
    glitch_xs    = rng.integers(0, w, 20)
    glitch_ws    = rng.integers(2, 10, 20)
    glitch_ph    = rng.uniform(0, 10, 20)
    neon_colors  = [
        (255, 0, 200), (0, 255, 255), (255, 50, 0),
        (180, 0, 255), (0, 200, 255),
    ]

    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Yavaş ilerleyen yatay tarama çizgileri
        for sy in scan_ys:
            y = int((sy + t * 25) % h)
            frame[y:y+1, :, 1] = 55
            frame[y:y+1, :, 2] = 75
        # Dikey neon flaşlar (belirli anlarda yanıyor)
        for i in range(20):
            if np.sin(t * 6.5 + glitch_ph[i]) > 0.80:
                col = neon_colors[i % len(neon_colors)]
                x0 = int(glitch_xs[i])
                x1 = min(w, x0 + int(glitch_ws[i]))
                frame[:, x0:x1, 0] = col[0] // 5
                frame[:, x0:x1, 1] = col[1] // 5
                frame[:, x0:x1, 2] = col[2] // 5
        return frame

    return VideoClip(make_frame, duration=duration)


# ── Yaprak Düşüşü Efekti ───────────────────────────────────────────────────────
def _make_leaves_clip(w, h, duration):
    rng = np.random.default_rng(99)
    N = 70
    xs_start  = rng.uniform(0, w, N)
    phases    = rng.uniform(0, h, N)
    speeds_y  = rng.uniform(40, 110, N)
    speeds_x  = rng.uniform(-25, 25, N)
    wobbles   = rng.uniform(15, 50, N)
    wob_freqs = rng.uniform(0.4, 1.8, N)
    leaf_cols = np.array([
        [80,  160,  60], [100, 180, 50],
        [180, 140,  30], [160, 100, 40],
        [200, 120,  35], [90,  150, 55],
    ], dtype=np.uint8)

    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        for i in range(N):
            y = int((phases[i] + t * speeds_y[i]) % (h + 20)) - 10
            x = int((xs_start[i] + t * speeds_x[i] +
                     wobbles[i] * np.sin(t * wob_freqs[i])) % w)
            col = leaf_cols[i % len(leaf_cols)]
            y0, y1 = max(0, y - 2), min(h, y + 3)
            x0, x1 = max(0, x - 2), min(w, x + 3)
            frame[y0:y1, x0:x1] = col
        return frame

    return VideoClip(make_frame, duration=duration)


# ── Efekt Klip Oluşturucu ──────────────────────────────────────────────────────
def _create_effect_clip(effect, w, h, duration):
    """Verilen efekt adına göre animasyonlu overlay klip üretir."""
    try:
        if effect == 'rain':
            clip = _make_rain_clip(w, h, duration)
            opacity = 0.38
        elif effect == 'stars':
            clip = _make_stars_clip(w, h, duration)
            opacity = 0.55
        elif effect == 'cyberpunk':
            clip = _make_cyberpunk_clip(w, h, duration)
            opacity = 0.45
        elif effect == 'leaves':
            clip = _make_leaves_clip(w, h, duration)
            opacity = 0.50
        else:
            return None

        # Opacity uygula (v2 / v1 uyumlu)
        try:
            return clip.with_opacity(opacity)
        except AttributeError:
            return clip.set_opacity(opacity)

    except Exception as err:
        print(f"Uyarı: Efekt klip oluşturulamadı ({effect}): {err}")
        return None


# ── Audio Reactive Equalizer ───────────────────────────────────────────────────
def _make_equalizer_clip(audio_path, w, h, duration, n_bars=48):
    """
    Ses dosyasını analiz ederek alt kısımda sese senkronize
    equalizer bar animasyonu üretir.
    """
    if HAS_LIBROSA:
        try:
            y_audio, sr = librosa.load(audio_path, sr=22050, mono=True, duration=None)
            hop_length  = 512
            # STFT spektrum
            stft = np.abs(librosa.stft(y_audio, hop_length=hop_length))
            # n_bars frekans grubuna böl
            freqs_per_bar = max(1, stft.shape[0] // n_bars)
            frames_total  = stft.shape[1]
            fps_audio     = sr / hop_length

            # Her bar için maksimum değer → normalize
            bar_data = np.zeros((n_bars, frames_total), dtype=np.float32)
            for b in range(n_bars):
                f0 = b * freqs_per_bar
                f1 = f0 + freqs_per_bar
                bar_data[b] = stft[f0:f1].mean(axis=0)

            # Global normalize
            peak = bar_data.max()
            if peak > 0:
                bar_data /= peak

            print("[EQ] Ses analizi tamamlandı, equalizer verisi hazır.")
            use_librosa = True
        except Exception as e:
            print(f"[EQ] Librosa analiz hatası: {e}")
            use_librosa = False
    else:
        use_librosa = False
        print("[EQ] Librosa yok — sabit animasyon kullanılıyor.")

    # Bar tasarım parametreleri
    bar_area_h  = int(h * 0.18)       # Ekranın altındaki %18
    bar_y_base  = h - 20              # Barlar nerede bitiyor
    bar_w       = max(4, (w - 60) // n_bars)
    bar_gap     = max(1, bar_w // 4)
    total_bar_w = (bar_w + bar_gap) * n_bars
    x_offset    = (w - total_bar_w) // 2
    max_bar_h   = bar_area_h - 20

    # Renk paleti: mor → cyan gradient
    def bar_color(bar_idx, intensity):
        t = bar_idx / n_bars
        r = int(112 + (0   - 112) * t)   # 112→0
        g = int(0   + (212 - 0  ) * t)   # 0→212
        b = int(255 + (255 - 255) * t)   # 255→255
        r = max(0, min(255, int(r * (0.4 + 0.6 * intensity))))
        g = max(0, min(255, int(g * (0.4 + 0.6 * intensity))))
        b = max(0, min(255, int(b * (0.4 + 0.6 * intensity))))
        return r, g, b

    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        if use_librosa:
            frame_idx = min(int(t * fps_audio), frames_total - 1)
            heights = (bar_data[:, frame_idx] * max_bar_h).astype(int)
        else:
            # Fallback: sinüs dalgası animasyonu
            heights = np.array([
                int(max_bar_h * 0.3 * abs(np.sin(t * 2.5 + b * 0.4 + np.sin(t + b * 0.2))))
                for b in range(n_bars)
            ])

        for b in range(n_bars):
            bh  = max(3, int(heights[b]))
            x0  = x_offset + b * (bar_w + bar_gap)
            x1  = x0 + bar_w
            y0  = bar_y_base - bh
            y1  = bar_y_base
            intensity = bh / max_bar_h
            r, g, bb = bar_color(b, intensity)

            if x1 <= w and y0 >= 0:
                # Bar gövdesi
                frame[y0:y1, x0:x1, 0] = r
                frame[y0:y1, x0:x1, 1] = g
                frame[y0:y1, x0:x1, 2] = bb
                # Üst kısım daha parlak (vurgu)
                cap_h = max(2, bh // 8)
                frame[y0:y0 + cap_h, x0:x1, 0] = min(255, r + 80)
                frame[y0:y0 + cap_h, x0:x1, 1] = min(255, g + 80)
                frame[y0:y0 + cap_h, x0:x1, 2] = min(255, bb + 60)

        return frame

    clip = VideoClip(make_frame, duration=duration)
    try:
        return clip.with_opacity(0.75)
    except AttributeError:
        return clip.set_opacity(0.75)


def _make_bottom_gradient(w, h, duration):
    """Alt kısımda equalizer bölgesini ayıran yumuşak karartma — sadece EQ alanı."""
    grad_h = int(h * 0.18)

    # Gradient frame'i bir kez hesapla (her frame aynı)
    _grad_frame = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(grad_h):
        intensity = int(180 * (i / grad_h) ** 1.2)   # 0→180, üste şeffaf altta koyu
        _grad_frame[h - grad_h + i, :, :] = intensity  # doğru alpha kullan

    def make_frame(t):
        return _grad_frame

    clip = VideoClip(make_frame, duration=duration)
    try:
        return clip.with_opacity(0.45)   # 0.7 → 0.45 (daha şeffaf)
    except AttributeError:
        return clip.set_opacity(0.45)


# ── Ana Video Motoru ───────────────────────────────────────────────────────────
class VideoEngine:
    def __init__(self):
        pass

    def create_video(self, audio_path, image_path, genre=None, output_path="final_video.mp4"):
        if not HAS_MOVIEPY:
            raise RuntimeError("MoviePy yuklu degil. Kur: pip install moviepy")
        print(f"--- Video Rendering Başladı (V2.x + EQ Animasyon): {output_path} ---")
        try:
            audio    = AudioFileClip(audio_path)
            duration = audio.duration

            # Temel görsel
            base_clip = ImageClip(image_path).with_duration(duration)
            w, h = base_clip.size

            # Ken Burns / Zoom Effect
            try:
                def zoom_in(t):
                    return 1.0 + (0.12 * t / duration)
                if hasattr(base_clip, 'resize'):
                    base_clip = base_clip.resize(zoom_in)
                elif hasattr(base_clip, 'resized'):
                    base_clip = base_clip.resized(zoom_in)
                base_clip = base_clip.with_position('center')
            except Exception as zoom_err:
                print(f"Uyarı: Zoom efekti uygulanamadı ({zoom_err})")

            # Siyah arka plan
            bg_clip = ColorClip(size=(w, h), color=(0, 0, 0)).with_duration(duration)
            final_elements = [bg_clip, base_clip]

            # Parçacık efekti (genre'a göre otomatik)
            effect_type = _detect_effect(genre or "")
            if effect_type:
                print(f"Parçacık efekti: {effect_type}")
                effect_clip = _create_effect_clip(effect_type, w, h, duration)
                if effect_clip:
                    final_elements.append(effect_clip)

            # Alt gradient karartma (EQ arkası için)
            try:
                grad = _make_bottom_gradient(w, h, duration)
                final_elements.append(grad)
            except Exception as e:
                print(f"[Video] Gradient olusturulamadi (devam edilecek): {e}")

            # Ses frekansına senkronize equalizer bars
            try:
                print("[EQ] Equalizer animasyonu oluşturuluyor...")
                eq_clip = _make_equalizer_clip(audio_path, w, h, duration)
                final_elements.append(eq_clip)
                print("[EQ] Equalizer hazır.")
            except Exception as eq_err:
                print(f"Uyarı: Equalizer oluşturulamadı: {eq_err}")

            video = CompositeVideoClip(final_elements, size=(w, h))
            video = video.with_audio(audio)

            # Fade in/out (3 saniye)
            try:
                video = video.fadein(3).fadeout(3)
                if video.audio:
                    try:
                        video = video.with_audio(video.audio.fadein(3).fadeout(3))
                    except Exception as e:
                        print(f"[Video] Audio fade efekti uygulanamadi (ses olduğu gibi): {e}")
            except Exception as fe:
                print(f"Uyarı: Fade efekti uygulanamadı: {fe}")

            video.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="veryfast",   # medium→veryfast: VPS'de 3x hızlı, kalite farkı minimal
                threads=2            # 4→2: stream FFmpeg ile CPU paylaşımı
            )

            print("--- Render Başarıyla Tamamlandı! ---")
            return output_path
        except Exception as e:
            print(f"--- Render Hatası: {e} ---")
            import traceback; traceback.print_exc()
            return None
        finally:
            # Memory leak önleme — tüm clip'leri kapat
            for _clip in [
                locals().get('audio'), locals().get('base_clip'),
                locals().get('bg_clip'), locals().get('effect_clip'),
                locals().get('grad'), locals().get('eq_clip'),
                locals().get('video')
            ]:
                if _clip is not None and hasattr(_clip, 'close'):
                    try: _clip.close()
                    except Exception: pass

    def create_shorts(self, video_path, output_path, duration=60):
        """Ana videodan 9:16 formatında YouTube Shorts kesiyor."""
        if not HAS_MOVIEPY:
            print("[Shorts] MoviePy yuklu degil, shorts olusturulamadi.")
            return False
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[create_shorts] Start: {video_path} -> {output_path}")
        print(f"--- Shorts Oluşturuluyor ({duration}s): {output_path} ---")
        clip = None
        short = None
        cropped = None
        try:
            clip = VideoFileClip(video_path)
            # İlk N saniyeyi al (video kısaysa tamamını)
            actual_duration = min(duration, clip.duration)
            short = clip.subclipped(0, actual_duration)

            # 9:16 krop (1080x1920 hedef, merkezden)
            w, h = short.size
            target_ratio = 9 / 16
            current_ratio = w / h
            if current_ratio > target_ratio:
                # Genişliği kırp
                new_w = int(h * target_ratio)
                x1 = (w - new_w) // 2
                logger.info(f"[create_shorts] Width crop: {w}x{h} -> {new_w}x{h}")
                try:
                    cropped = short.cropped(x1=x1, x2=x1 + new_w)
                except AttributeError:
                    cropped = short.crop(x1=x1, x2=x1 + new_w)
            elif current_ratio < target_ratio:
                # Yüksekliği kırp
                new_h = int(w / target_ratio)
                y1 = (h - new_h) // 2
                logger.info(f"[create_shorts] Height crop: {w}x{h} -> {w}x{new_h}")
                try:
                    cropped = short.cropped(y1=y1, y2=y1 + new_h)
                except AttributeError:
                    cropped = short.crop(y1=y1, y2=y1 + new_h)
            else:
                cropped = short

            cropped.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="fast",
                threads=4
            )
            result = os.path.exists(output_path)
            logger.info(f"[create_shorts] Done. Output exists: {result}")
            print("--- Shorts Tamamlandı! ---")
            return result
        except Exception as e:
            logger.error(f"[create_shorts] Error: {e}")
            print(f"--- Shorts Hatası: {e} ---")
            return False
        finally:
            for c in [cropped, short, clip]:
                if c is not None:
                    try:
                        c.close()
                    except Exception as e:
                        print(f"[Shorts] Clip kapatılamadı: {e}")
