# MoviePy v2.x Uyumlu Video Motoru
try:
    from moviepy import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
except ImportError:
    # Eski versiyonlar için fallback
    try:
        from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
    except ImportError:
        pass

import os

class VideoEngine:
    def __init__(self):
        pass

    def create_video(self, audio_path, image_path, lyrics=None, output_path="final_video.mp4"):
        print(f"--- Video Rendering Başladı (V2.x): {output_path} ---")
        try:
            audio = AudioFileClip(audio_path)
            duration = audio.duration
            
            # Temel görsel
            base_clip = ImageClip(image_path).with_duration(duration)
            w, h = base_clip.size
            
            # Ken Burns / Zoom Effect (Yavaşça yakınlaştırma)
            try:
                def zoom_in(t):
                    # %15 yakınlaştırma (1.0 -> 1.15)
                    return 1.0 + (0.15 * t / duration)
                
                # moviepy v1 ve v2 uyumluluğu için
                if hasattr(base_clip, 'resize'):
                    base_clip = base_clip.resize(zoom_in)
                elif hasattr(base_clip, 'resized'):
                    base_clip = base_clip.resized(zoom_in)
                
                # Büyüyen resmi merkeze sabitle ki taşmasın
                base_clip = base_clip.with_position('center')
            except Exception as zoom_err:
                print(f"Uyarı: Zoom efekti uygulanamadı ({zoom_err})")
            
            # Siyah arka plan (zoom esnasında taşılan yerler siyah dolsun)
            bg_clip = ColorClip(size=(w, h), color=(0,0,0)).with_duration(duration)
            
            final_elements = [bg_clip, base_clip]
            
            # Altyazı / Lirikler
            if lyrics:
                try:
                    # Gölgeli veya arkaplanlı okunaklı TextClip
                    txt_clip = TextClip(
                        text=lyrics, 
                        font="Arial-Bold",
                        font_size=60, 
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        method='caption',
                        size=(w - 100, None),
                        duration=duration
                    ).with_position(('center', 'bottom'))
                    
                    # Alt kısımdan biraz yukarıda dursun
                    txt_clip = txt_clip.with_position(lambda t: ('center', h - txt_clip.h - 80))
                    final_elements.append(txt_clip)
                except Exception as text_err:
                    print(f"Uyarı: TextClip oluşturulamadı (ImageMagick eksik olabilir). Hata: {text_err}")

            video = CompositeVideoClip(final_elements, size=(w, h))
            video = video.with_audio(audio)
            
            # Render
            video.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                preset="medium",
                threads=4
            )
            
            print("--- Render Başarıyla Tamamlandı! ---")
            return output_path
        except Exception as e:
            print(f"--- Render Hatası: {e} ---")
            return None
