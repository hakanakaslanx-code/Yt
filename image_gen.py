import replicate
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Replicate Settings
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

class ImageGenerator:
    def __init__(self, api_token=None):
        self.api_token = api_token or REPLICATE_API_TOKEN
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

    def generate_image(self, prompt, output_name="background.jpg", style="Cinematic"):
        """
        Flux Schnell modelini kullanarak görüntü üretir.
        Gelen style text'ini prompt'a entegre eder.
        """
        if not self.api_token:
            print("Hata: REPLICATE_API_TOKEN bulunamadı.")
            return None

        # Stil haritası
        style_modifiers = {
            "Cinematic": "cinematic lighting, highly detailed, 8k resolution, photorealistic, epic composition",
            "Anime": "anime style, studio ghibli, makoto shinkai, vibrant colors, detailed anime art",
            "Cyberpunk": "cyberpunk aesthetic, neon lights, dystopian futuristic city, dark synthwave vibe",
            "Realistic": "ultra realistic, raw photo, DSLR 85mm, natural lighting, highly detailed",
            "Digital Art": "trending on artstation, masterpiece, intricate details, fantasy digital painting"
        }

        # Stile göre promptu zenginleştir
        modifier = style_modifiers.get(style, style_modifiers["Cinematic"])
        final_prompt = f"{prompt}, {modifier}"

        print(f"Görsel üretiliyor: {final_prompt}")
        try:
            # Flux Schnell Modeli
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": final_prompt,
                    "aspect_ratio": "16:9",
                    "output_format": "jpg",
                    "output_quality": 90
                }
            )
            
            # Replicate liste olarak döner
            image_url = output[0] if isinstance(output, list) else output
            print(f"Görsel hazır: {image_url}")
            
            # İndir ve kaydet
            self.download_file(image_url, output_name)
            return output_name
        except Exception as e:
            print(f"Görsel üretim hatası: {e}")
            return None

    def download_file(self, url, filename):
        r = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(r.content)
        print(f"Görsel kaydedildi: {filename}")

if __name__ == "__main__":
    # Test
    if not REPLICATE_API_TOKEN:
        print("Lütfen .env dosyasına REPLICATE_API_TOKEN ekleyin.")
    else:
        gen = ImageGenerator()
        # gen.generate_image("A futuristic cyberpunk city with neon lights, lo-fi aesthetic, 4k", "test_img.jpg")
        print("Resim motoru hazır.")
