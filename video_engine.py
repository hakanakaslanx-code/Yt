from moviepy.editor import ImageClip, AudioFileClip
import os

class VideoEngine:
    def __init__(self):
        pass

    def create_video(self, audio_path, image_path, output_path="final_video.mp4"):
        """
        Müzik ve Resmi birleştirip MP4 video oluşturur.
        """
        print(f"Video oluşturuluyor: {output_path}")
        try:
            # Sesi yükle
            audio = AudioFileClip(audio_path)
            
            # Resmi yükle ve süresini sesle eşitle
            clip = ImageClip(image_path).set_duration(audio.duration)
            
            # Sesi videoya ekle
            clip = clip.set_audio(audio)
            
            # FPS ayarla ve kaydet
            clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
            
            print("Video başarıyla üretildi!")
            return output_path
        except Exception as e:
            print(f"Video üretim hatası: {e}")
            return None

if __name__ == "__main__":
    # Test
    # engine = VideoEngine()
    # engine.create_video("test_music.mp3", "test_img.jpg", "test_video.mp4")
    print("Video motoru hazır.")
