import replicate
import os
import requests
from dotenv import load_dotenv

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
            "Digital Art": "trending on artstation, masterpiece, intricate details, fantasy digital painting",
            "80s": "1980s retro aesthetic, VHS film grain, neon glow, synthwave colors, vintage photography style",
        }

        # Stile göre promptu zenginleştir
        modifier = style_modifiers.get(style, style_modifiers["Cinematic"])
        final_prompt = f"{prompt}, {modifier}"

        print(f"Görsel üretiliyor: {final_prompt}")
        try:
            # Flux 1.1 Pro Modeli
            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "prompt": final_prompt,
                    "aspect_ratio": "16:9",
                    "output_format": "jpg",
                    "output_quality": 95,
                    "prompt_upsampling": True
                }
            )
            
            # Replicate eski sürümlerde liste, yeni sürümlerde FileOutput döner
            if isinstance(output, list):
                raw = output[0]
            else:
                raw = output
            # FileOutput nesnesi URL'ye dönüştürülür
            image_url = str(raw) if not isinstance(raw, str) else raw
            print(f"Görsel hazır: {image_url}")

            # İndir ve kaydet
            self.download_file(image_url, output_name)
            return output_name, image_url
        except Exception as e:
            print(f"Görsel üretim hatası: {e}")
            return None, None

    def download_file(self, url, filename):
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(r.content)
        print(f"Görsel kaydedildi: {filename}")

    # Genre → renk ve glow paleti
    _GENRE_PALETTE = {
        'jazz':       {'text': (255, 215,  90), 'glow': (180, 120,   0)},
        'lofi':       {'text': (255, 170, 220), 'glow': (160,  40, 140)},
        'cyberpunk':  {'text': (  0, 240, 255), 'glow': (  0, 100, 220)},
        'synthwave':  {'text': (  0, 240, 255), 'glow': (  0, 100, 220)},
        '80s':        {'text': (255, 220,  45), 'glow': (200,  90,   0)},
        'ambient':    {'text': (180, 220, 255), 'glow': ( 40,  90, 200)},
        'classical':  {'text': (255, 248, 230), 'glow': (180, 150, 100)},
        'electronic': {'text': (  0, 220, 255), 'glow': (  0, 100, 200)},
        'rock':       {'text': (255,  90,  45), 'glow': (180,  20,   0)},
        'pop':        {'text': (255, 100, 200), 'glow': (200,   0, 150)},
        'r&b':        {'text': (255, 200,  90), 'glow': (180,  90,   0)},
        'hip':        {'text': (255, 255, 255), 'glow': ( 80,  80,  80)},
        'afro':       {'text': (255, 220, 110), 'glow': (160,  90,   0)},
        'house':      {'text': (255, 200,  80), 'glow': (160,  80,   0)},
        'country':    {'text': (255, 210, 120), 'glow': (160, 100,  20)},
        'reggae':     {'text': ( 80, 220,  80), 'glow': (  0, 140,  40)},
        'meditation': {'text': (190, 190, 255), 'glow': ( 60,  60, 200)},
        'sleep':      {'text': (150, 180, 255), 'glow': ( 40,  60, 160)},
        'study':      {'text': (180, 255, 200), 'glow': ( 20, 160,  80)},
        'workout':    {'text': (255,  80,  80), 'glow': (200,   0,   0)},
    }

    def _get_palette(self, category_text):
        if not category_text:
            return {'text': (255, 255, 255), 'glow': (100, 100, 100)}
        c = category_text.lower()
        for key, pal in self._GENRE_PALETTE.items():
            if key in c:
                return pal
        return {'text': (255, 255, 255), 'glow': (80, 80, 80)}

    def add_thumbnail_overlay(self, image_path, category_text, output_path=None):
        """
        Referans kanallar gibi: büyük genre ismi + alt gradient.
        category_text: gösterilecek kısa isim (örn. 'Jazz', 'Afro House', '80s Music')
        """
        if not HAS_PIL:
            print("[Thumbnail] PIL yüklü değil, overlay atlanıyor.")
            return image_path

        output_path = output_path or image_path
        try:
            img = Image.open(image_path).convert("RGBA")
            W, H = img.size

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Alt gradient — hafif karartma (sadece metin okunabilirliği için)
            grad_h = int(H * 0.35)
            for i in range(grad_h):
                pct   = i / grad_h
                alpha = int(150 * (pct ** 1.6))   # üstte çok hafif, altta orta
                draw.rectangle([(0, H - grad_h + i), (W, H - grad_h + i + 1)],
                                fill=(0, 0, 0, alpha))

            # Font — en büyük mevcut bold font
            font_paths = [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            ]

            # Yazı büyüklüğü: görüntü yüksekliğinin %17 ile %20'si
            font_size = int(H * 0.17)
            font = None
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        break
                    except Exception:
                        pass
            if font is None:
                font = ImageFont.load_default()

            # Sadece kategori adı göster (max 3 kelime, 2 satır)
            display = category_text.strip().upper()
            words   = display.split()
            lines, line = [], []
            for w in words:
                test = ' '.join(line + [w])
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] > W * 0.85 and line:
                    lines.append(' '.join(line))
                    line = [w]
                else:
                    line.append(w)
            if line:
                lines.append(' '.join(line))
            lines = lines[:2]

            palette    = self._get_palette(category_text)
            text_color = palette['text'] + (255,)
            glow_color = palette['glow'] + (160,)

            line_h  = int(font_size * 1.15)
            total_h = len(lines) * line_h
            # Alt kısımda konumlandır — gradyanın ortası-aşağısı
            y_start = H - int(grad_h * 0.48) - total_h // 2

            for ln in lines:
                bbox = draw.textbbox((0, 0), ln, font=font)
                tw   = bbox[2] - bbox[0]
                x    = (W - tw) // 2        # ortalanmış

                # Glow katmanları (5 geçiş, dıştan içe)
                for off in [8, 6, 4, 3, 2]:
                    for dx in [-off, 0, off]:
                        for dy in [-off, 0, off]:
                            draw.text((x + dx, y_start + dy), ln, font=font, fill=glow_color)

                # Siyah derin gölge
                draw.text((x + 4, y_start + 4), ln, font=font, fill=(0, 0, 0, 220))
                draw.text((x + 2, y_start + 2), ln, font=font, fill=(0, 0, 0, 180))

                # Ana yazı
                draw.text((x, y_start), ln, font=font, fill=text_color)
                y_start += line_h

            result = Image.alpha_composite(img, overlay).convert("RGB")
            result.save(output_path, "JPEG", quality=95)
            print(f"[Thumbnail] Overlay eklendi: {output_path}")
            return output_path
        except Exception as e:
            print(f"[Thumbnail] Overlay hatası: {e}")
            return image_path

if __name__ == "__main__":
    # Test
    if not REPLICATE_API_TOKEN:
        print("Lütfen .env dosyasına REPLICATE_API_TOKEN ekleyin.")
    else:
        gen = ImageGenerator()
        # gen.generate_image("A futuristic cyberpunk city with neon lights, lo-fi aesthetic, 4k", "test_img.jpg")
        print("Resim motoru hazır.")
