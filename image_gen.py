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

    def generate_image(self, prompt, output_name="background.jpg"):
        """
        Flux Schnell modelini kullanarak görüntü üretir.
        """
        if not self.api_token:
            print("Hata: REPLICATE_API_TOKEN bulunamadı.")
            return None

        print(f"Görsel üretiliyor: {prompt}")
        try:
            # Flux Schnell Modeli
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
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
