from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, session
import os
import json
import threading
import queue as _queue_mod
import time
import traceback
import subprocess
from dotenv import load_dotenv, set_key

load_dotenv()

# ── Scheduler ─────────────────────────────────────────
HAS_SCHEDULER = False
try:
    from scheduler import (init_scheduler, list_schedules, get_schedule,
                            add_schedule, update_schedule, delete_schedule,
                            toggle_schedule, run_now as sched_run_now)
    HAS_SCHEDULER = True
except ImportError as e:
    print(f"[WARN] Scheduler module missing: {e}")

# ── Safe module imports ───────────────────────────────
HAS_MODULES = False
try:
    from music_gen import MusicGenerator
    from image_gen import ImageGenerator
    from video_engine import VideoEngine
    from yt_auth import (get_auth_url, exchange_code, get_channel_info, is_connected,
                          load_channels, set_default_channel, remove_channel, get_default_channel)
    from uploader import (upload_video, generate_seo_metadata, set_thumbnail,
                          get_or_create_playlist, add_video_to_playlist,
                          update_live_broadcast_title, get_or_create_live_stream_key,
                          get_quota_usage)
    from streamer import (start_stream, stop_stream, get_status as stream_status,
                          is_ffmpeg_installed, start_stream_playlist, download_bg_video,
                          get_all_statuses)
    from telegram_notify import notify_uploaded, notify_error, notify_shorts_uploaded, notify_weekly_report
    HAS_MODULES = True
except ImportError as e:
    print(f"[WARN] Module missing: {e}")

if not HAS_MODULES:
    def is_connected(slug=None): return False
    def get_channel_info(slug=None): return None, "Modules not loaded"
    def load_channels(): return []
    def set_default_channel(s): pass
    def remove_channel(s): return None
    def get_default_channel(): return None
    def stream_status(*a, **kw): return {"active": False, "key": None, "started": None, "video": None}
    def get_all_statuses(): return []
    def is_ffmpeg_installed(): return False
    def start_stream(*a, **kw): return False, "Modules not loaded"
    def stop_stream(*a, **kw): return False, "Modules not loaded"
    def download_bg_video(*a, **kw): return False, "Modules not loaded"
    def generate_seo_metadata(g, s, **kw): return f"{g} Mix", "AI Generated", ["ai"]
    def upload_video(*a, **kw): return None
    def set_thumbnail(*a, **kw): return False
    def get_or_create_playlist(*a, **kw): return None
    def add_video_to_playlist(*a, **kw): return False
    def notify_uploaded(*a, **kw): pass
    def notify_error(*a, **kw): pass
    def notify_shorts_uploaded(*a, **kw): pass
    def notify_weekly_report(*a, **kw): pass
    def start_stream_playlist(*a, **kw): return False, "Modules not loaded"
    def update_live_broadcast_title(*a, **kw): return False, "Modules not loaded"
    def get_quota_usage(): return {"used": 0, "limit": 10000, "remaining": 10000, "date": ""}

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'allone-secret-key-2024')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024   # 2 GB limit
app.config['MAX_FORM_MEMORY_SIZE'] = 1 * 1024 * 1024   # 1MB threshold — üstü diske yaz, RAM'de tutma

# ── Auth ───────────────────────────────────────────────
from functools import wraps

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'allone2024')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ── Paths ──────────────────────────────────────────────
_base_dir = os.environ.get('APP_BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
ENV_FILE   = os.environ.get('ENV_FILE',   os.path.join(_base_dir, '.env'))
VIDEOS_DIR = os.environ.get('VIDEOS_DIR', os.path.join(_base_dir, 'outputs'))
TASKS_FILE  = os.path.join(_base_dir, 'tasks.json')
STREAM_KEYS_FILE = os.path.join(_base_dir, 'stream_keys.json')
os.makedirs(VIDEOS_DIR, exist_ok=True)

# ── Task Persistence ──────────────────────────────────
_tasks_lock = threading.Lock()

# ── Video Production Queue ─────────────────────────────
# Aynı anda sadece MAX_CONCURRENT_JOBS video üretilir, geri kalanlar sıraya girer
MAX_CONCURRENT_JOBS = int(os.getenv('MAX_CONCURRENT_JOBS', '1'))
_prod_queue    = _queue_mod.Queue()
_active_jobs   = 0
_active_lock   = threading.Lock()

def _queue_worker():
    """Arka planda sürekli çalışır, kuyruktan iş alır."""
    global _active_jobs
    try:
        os.nice(10)   # render thread'ini düşük CPU önceliğine al
    except Exception:
        pass
    while True:
        job = _prod_queue.get()       # (fn, args, kwargs, task_ref)
        fn, args, kwargs, task_ref = job
        with _active_lock:
            _active_jobs += 1
        try:
            fn(*args, **kwargs)
        except Exception as e:
            print(f"[Queue] Job hatası: {e}")
        finally:
            with _active_lock:
                _active_jobs -= 1
            _prod_queue.task_done()
            # Kuyrukta bekleyenlerin pozisyonunu güncelle
            _refresh_queue_positions()

def _refresh_queue_positions():
    """Kuyrukta bekleyen task'ların status'unu günceller."""
    with _tasks_lock:
        waiting = [t for t in current_tasks if t.get('status', '').startswith('Queue:')]
        for i, t in enumerate(waiting, 1):
            t['status'] = f'Queue: {i}. sırada bekliyor'
        if waiting:
            save_tasks(current_tasks)

def _enqueue_flow(task_ref, fn, *args, **kwargs):
    """Görevi kuyruğa ekler — her zaman queue üzerinden çalışır (limit doğru çalışsın)."""
    _prod_queue.put((fn, args, kwargs, task_ref))

# Queue worker'ı başlat
for _ in range(MAX_CONCURRENT_JOBS):
    threading.Thread(target=_queue_worker, daemon=True).start()

def load_tasks():
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_tasks(tasks):
    try:
        tmp = TASKS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(tasks, f, indent=2)
        os.replace(tmp, TASKS_FILE)
    except Exception as e:
        print(f"[WARN] Could not save tasks: {e}")

# ── Bootstrap data ────────────────────────────────────
_loaded_tasks = load_tasks()
current_tasks = _loaded_tasks

stats = {
    "total_videos": len([t for t in current_tasks if t.get("file")]),
    "credits_used": "$14.50",
    "active_streams": 0
}


# ── Helpers ───────────────────────────────────────────
def get_file_list(ext):
    try:
        files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(ext)]
        return sorted(files, reverse=True)
    except Exception:
        return []

def file_info(filename):
    path = os.path.join(VIDEOS_DIR, filename)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    if size > 1024 * 1024:
        return {"name": filename, "size": f"{size // (1024*1024)} MB"}
    return {"name": filename, "size": f"{size // 1024} KB"}

def safe_get_yt_channel():
    try:
        if is_connected():
            info, err = get_channel_info()
            if info and not err:
                return info
    except Exception as e:
        print(f"[WARN] YouTube channel info error: {e}")
    return None

# ── Stream Key Persistence ─────────────────────────────
def load_stream_keys():
    try:
        if os.path.exists(STREAM_KEYS_FILE):
            with open(STREAM_KEYS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_stream_keys(keys: dict):
    try:
        with open(STREAM_KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save stream keys: {e}")

# ── Kategori Normalizasyonu ────────────────────────────
_CATEGORY_RULES = [
    (['jazz', 'saxophone', 'sax', 'bebop', 'swing', 'blues'],              'Jazz'),
    (['lofi', 'lo-fi', 'lo fi', 'chill beats', 'hip hop beat', 'hiphop'],  'Lofi'),
    (['80s', '80\'s', 'eighties', 'retro pop', 'retrowave', 'cassette', 'arcade', 'vhs'], '80s'),
    (['cyberpunk', 'synthwave', 'neon', 'darksynth', 'vaporwave', 'cyber'],    'Cyberpunk'),
    (['meditation', 'zen', 'mindfulness', 'yoga', 'healing'],              'Meditation'),
    (['sleep', 'insomnia', 'deep sleep', 'sleeping'],                       'Sleep'),
    (['study', 'focus', 'concentration', 'coding', 'work'],                 'Study'),
    (['rain', 'storm', 'thunder', 'drizzle'],                               'Rain Ambient'),
    (['forest', 'nature', 'birds', 'woodland', 'leaves'],                   'Nature Ambient'),
    (['space', 'cosmic', 'galaxy', 'nebula', 'universe'],                   'Space Ambient'),
    (['dark', 'dark ambient', 'horror', 'eerie', 'shadow'],                 'Dark Ambient'),
    (['piano', 'classical piano', 'acoustic piano'],                        'Piano'),
    (['classical', 'orchestra', 'orchestral', 'symphony', 'cinematic'],     'Cinematic'),
    (['anime', 'japanese', 'jpop', 'j-pop', 'kawaii'],                      'Anime'),
    (['epic', 'powerful', 'battle', 'war', 'heroic'],                       'Epic'),
    (['trap', 'drill', 'bass', 'bouncy'],                                    'Trap'),
    (['rock', 'guitar', 'electric guitar', 'metal', 'punk'],                'Rock'),
    (['reggae', 'ska', 'dub'],                                              'Reggae'),
    (['funk', 'soul', 'groove', 'r&b', 'rnb'],                              'Soul & Funk'),
    (['ambient', 'atmospheric', 'drone', 'pad'],                            'Ambient'),
    (['chill', 'relax', 'smooth', 'mellow', 'calm'],                        'Chill'),
]

def normalize_category(genre_text: str) -> str:
    """Ham genre promptundan geniş kategori adı üretir."""
    if not genre_text:
        return 'Other'
    t = genre_text.lower()
    for keywords, category in _CATEGORY_RULES:
        if any(k in t for k in keywords):
            return category
    # Fallback: ilk kelimeyi capitalize et
    return genre_text.strip().split()[0].title() if genre_text.strip() else 'Other'

# ── Music Prompt Builder ───────────────────────────────
import random as _random

# Prompt rotation — son kullanılan promptları takip et (tekrar önleme)
_used_prompts: list = []
_MAX_PROMPT_HISTORY = 20

# Her genre için: (prompt, suno_style, title_prefix, negative_tags)
_MUSIC_PROMPTS = {
    'lofi': [
        ("soft piano melody over lo-fi hip hop beat, warm jazz chords, dusty vinyl crackle, mellow bass guitar, late night study atmosphere, 75 BPM",
         "Lo-Fi Hip Hop, Chill, Jazz-Influenced",
         "Late Night Lofi",
         "Heavy Metal, Hard Rock, Aggressive Drums, Distortion"),
        ("Rhodes electric piano, lazy jazz guitar riff, soft hi-hats, rain in background, smooth bass, melancholic melody, 80 BPM",
         "Lo-Fi, Chillhop, Dreamy",
         "Rainy Day Lofi",
         "Heavy Metal, EDM, Loud, Harsh"),
        ("plucked guitar melody, muffled drums, record crackle, nostalgic piano chords, soft bass groove, cozy bedroom, 70 BPM",
         "Lo-Fi Beats, Nostalgic, Cozy",
         "Cozy Lofi Beats",
         "Heavy Metal, Trap, Aggressive"),
    ],
    '80s': [
        ("pulsing analog synthesizer lead melody, driving bass sequencer, gated reverb drums, arpeggiated synth chords, neon retrowave, 110 BPM",
         "Synthwave, 80s Retro, Cinematic",
         "Neon Drive 80s",
         "Acoustic Guitar, Jazz, Lo-Fi, Mellow"),
        ("electric piano chords, synth brass stabs, punchy drum machine, melodic synth lead, warm chorus effect, uplifting, 100 BPM",
         "80s Pop, Retro Electronic, Upbeat",
         "80s Retro Vibes",
         "Heavy Metal, Jazz, Acoustic, Slow"),
        ("lush synth pads, pulsating bass line, glittering arpeggios, analog drum machine, slow burning melody, retrofuturistic, 95 BPM",
         "Synthwave, Retrowave, Atmospheric",
         "Synthwave Nights",
         "Acoustic, Unplugged, Jazz, Heavy"),
    ],
    'jazz': [
        ("solo saxophone melody, upright bass walking line, brushed snare drums, jazz piano chord voicings, late night jazz club, 90 BPM",
         "Smooth Jazz, Contemporary Jazz, Instrumental",
         "Late Night Jazz",
         "Heavy Metal, Electronic, EDM, Hip Hop"),
        ("expressive jazz piano melody, walking bass, light cymbal work, bebop influenced chords, blue note mood, 100 BPM",
         "Jazz Piano, Bebop, Sophisticated",
         "Jazz Piano Sessions",
         "Electronic, Hip Hop, Metal, Distorted"),
        ("muted trumpet melody, organ comping, soft ride cymbal, slow cool jazz groove, Miles Davis inspired, smoky, 80 BPM",
         "Cool Jazz, Modal Jazz, Atmospheric",
         "Midnight Cool Jazz",
         "Electronic, Metal, Punk, Upbeat Pop"),
    ],
    'classical': [
        ("gentle flowing piano melody, soft string ensemble, emotional harmonic progression, Ludovico Einaudi style, cinematic, 60 BPM",
         "Neoclassical, Contemporary Classical, Cinematic",
         "Neoclassical Piano",
         "Electronic Drums, Bass Drop, Metal, Hip Hop"),
        ("solo piano nocturne, rich bass notes, delicate treble melody, soft pedal sustain, romantic era, intimate, 55 BPM",
         "Solo Piano, Romantic Classical, Emotional",
         "Piano Nocturne",
         "Drums, Electronic, Metal, Urban"),
        ("sweeping violin melody, cello harmony, light piano accents, gradual dynamic build, Hans Zimmer style, epic, 70 BPM",
         "Orchestral, Epic Classical, Cinematic",
         "Cinematic Orchestra",
         "Electronic Drums, Bass, Metal, Hip Hop"),
    ],
    'afro': [
        ("plucked kora melody, deep sub bass kick, layered congas, warm afro piano chords, melodic vocal chops, soulful, 122 BPM",
         "Afro House, Deep House, Tribal",
         "Afro House Sunset",
         "Heavy Metal, Classical, Acoustic Folk, Slow"),
        ("afro piano chords, organic percussion, deep bass groove, tribal rhythms, sunset energy, 120 BPM",
         "Afrobeats, Afro House, Spiritual",
         "Tribal Afro Groove",
         "Metal, Classical, Slow Ballad"),
    ],
    'cyberpunk': [
        ("aggressive synth lead over industrial drum pattern, distorted bass, glitchy FX, neon rain atmosphere, dark futuristic, 120 BPM",
         "Dark Synthwave, Cyberpunk, Industrial",
         "Cyberpunk Neon",
         "Acoustic Guitar, Jazz, Classical, Cheerful"),
        ("heavy synth bass, cold arpeggiated lead melody, cinematic tension build, blade runner aesthetic, brooding, 115 BPM",
         "Dark Electro, Atmospheric Synth, Dystopian",
         "Dark Synthwave",
         "Acoustic, Happy, Jazz, Classical"),
    ],
    'ambient': [
        ("slowly evolving synth pads, soft reverb piano notes, gentle nature soundscape, tibetan bowl overtones, no drums, peaceful, 55 BPM",
         "Ambient, Meditation, Healing",
         "Ambient Meditation",
         "Drums, Bass Drop, Metal, Upbeat, Aggressive"),
        ("ethereal synth textures, distant piano, soft wind sounds, slow harmonic movement, zen, floating, 50 BPM",
         "Drone Ambient, Atmospheric, Zen",
         "Ethereal Ambience",
         "Drums, Hip Hop, Metal, Dance"),
    ],
    'deep house': [
        ("warm sub bass, soulful piano chord stabs, smooth organ melody, four-on-the-floor kick, deep groove, sunset rooftop, 120 BPM",
         "Deep House, Soulful House, Melodic",
         "Deep House Sessions",
         "Heavy Metal, Jazz Solo, Classical, Acoustic"),
        ("plucked guitar sample, deep kick, smooth synth melody, rolling bass line, beach sunset, warm, hypnotic, 122 BPM",
         "Melodic House, Progressive, Atmospheric",
         "Melodic Deep House",
         "Metal, Classical, Loud, Aggressive"),
    ],
}

def _build_music_prompt(genre: str, style: str = 'Cinematic') -> dict:
    """
    Genre'ya göre Suno AI için zengin prompt dict döner.
    Returns: {prompt, style, title, negative_tags}
    """
    g = genre.lower()
    if any(k in g for k in ['lofi', 'lo-fi', 'chill', 'hip hop', 'study']):
        pool = _MUSIC_PROMPTS['lofi']
    elif any(k in g for k in ['80s', "80'", 'eighties', 'synthwave', 'retro', 'vhs', 'neon drive']):
        pool = _MUSIC_PROMPTS['80s']
    elif any(k in g for k in ['jazz', 'saxophone', 'bebop', 'swing', 'blues']):
        pool = _MUSIC_PROMPTS['jazz']
    elif any(k in g for k in ['classical', 'piano', 'orchestra', 'string', 'violin', 'nocturne']):
        pool = _MUSIC_PROMPTS['classical']
    elif any(k in g for k in ['afro', 'tribal', 'kora', 'african']):
        pool = _MUSIC_PROMPTS['afro']
    elif any(k in g for k in ['cyber', 'dystopian', 'industrial', 'dark synth']):
        pool = _MUSIC_PROMPTS['cyberpunk']
    elif any(k in g for k in ['ambient', 'meditation', 'zen', 'drone', 'nature']):
        pool = _MUSIC_PROMPTS['ambient']
    elif any(k in g for k in ['deep house', 'house', 'progressive', 'melodic']):
        pool = _MUSIC_PROMPTS['deep house']
    else:
        return {
            "prompt": f"expressive lead melody, harmonic chord progressions, {genre}, dynamic arrangement, emotional depth",
            "style":  f"{genre}, Instrumental, {style}",
            "title":  f"{genre.title()} Mix",
            "negative_tags": "Heavy Metal, Distortion, Aggressive Drums, Screaming",
        }
    # Kullanılmamış promptları tercih et (rotation)
    unused = [p for p in pool if p[0] not in _used_prompts]
    candidates = unused if unused else pool
    prompt_txt, suno_style, title_prefix, neg = _random.choice(candidates)
    # Kullanılan promptu kaydet
    _used_prompts.append(prompt_txt)
    if len(_used_prompts) > _MAX_PROMPT_HISTORY:
        _used_prompts.pop(0)
    return {
        "prompt":        prompt_txt,
        "style":         suno_style,
        "title":         title_prefix,
        "negative_tags": neg,
    }


# ── Tag helpers ────────────────────────────────────────
def get_tags_map():
    """Görevlerden kategori→[video_path] haritası üretir. Raw prompt yerine geniş kategori kullanır."""
    with _tasks_lock:
        tasks_snap = list(current_tasks)
    tags: dict[str, list] = {}
    for t in tasks_snap:
        # Manuel kategori varsa onu kullan, yoksa otomatik normalize et
        category = (t.get('category') or normalize_category(t.get('genre', ''))).strip()
        vfile = t.get('file')
        if not vfile:
            continue
        vpath = os.path.join(VIDEOS_DIR, vfile)
        if not os.path.exists(vpath):
            continue
        tags.setdefault(category, []).append(vpath)
    return tags

def _next_task_id():
    """Thread-safe next ID (must be called inside _tasks_lock)."""
    if not current_tasks:
        return 1
    return max(t.get('id', 0) for t in current_tasks) + 1

# ── Automation Flow ───────────────────────────────────
def run_automation_flow(genre, style='Cinematic', lyrics_enabled=True, auto_upload=True, channel_slug=None, min_duration=0):
    with _tasks_lock:
        task_id = _next_task_id()
        task = {
            "id": task_id, "name": f"{genre} Video Forge",
            "status": "Initializing...", "file": None,
            "yt_url": None, "genre": genre, "style": style,
            "image_url": None, "category": normalize_category(genre),
            "channel_slug": channel_slug or "",   # kaydet — retry'da doğru kanal kullanılsın
        }
        current_tasks.append(task)
        save_tasks(current_tasks)

    def _update(status):
        task["status"] = status
        with _tasks_lock:
            save_tasks(current_tasks)

    try:
        if not HAS_MODULES:
            _update("Error: Server modules not loaded")
            return

        kie_key      = os.getenv('KIE_API_KEY')
        replicate_key = os.getenv('REPLICATE_API_TOKEN')
        if not kie_key or not replicate_key:
            _update("Error: API Keys Missing — go to Settings")
            return

        # 1) Music
        mg    = MusicGenerator(kie_key)
        audio = os.path.join(VIDEOS_DIR, f"music_{task_id}.mp3")
        mp    = _build_music_prompt(genre, style)   # dict: prompt, style, title, negative_tags
        # Tam dict'i sakla — retry'da kalite parametreleri korunsun
        with _tasks_lock:
            task["music_params"] = mp                       # retry için tam dict
            task["music_prompt"] = mp.get("prompt", "")    # SEO metadata için text
            save_tasks(current_tasks)
        if os.path.exists(audio):
            _update("Music ready (cached), skipping generation...")
        elif min_duration and min_duration > 0:
            _update(f"Generating Music (min {min_duration//60}min)...")
            ok = mg.generate_to_min_duration(mp["prompt"], audio, min_seconds=min_duration,
                                             style=mp.get("style"), title=mp.get("title"),
                                             negative_tags=mp.get("negative_tags"))
            if not ok or not os.path.exists(audio):
                _update("Error: Music generation failed")
                return
        else:
            _update("Generating Music...")
            mid = mg.generate_music(mp["prompt"], style=mp.get("style"),
                                    title=mp.get("title"), negative_tags=mp.get("negative_tags"))
            if not mid:
                _update("Error: Music generation failed")
                return
            mg.wait_and_download(mid, audio)
            if not os.path.exists(audio):
                _update("Error: Audio file not downloaded")
                return

        # Ses normalizasyonu: -14 LUFS (YouTube standardı — daha profesyonel ses)
        try:
            norm_tmp = audio + '.norm.mp3'
            subprocess.run([
                'ffmpeg', '-y', '-i', audio,
                '-af', 'loudnorm=I=-14:TP=-1:LRA=11',
                '-ar', '44100', '-b:a', '192k', norm_tmp
            ], capture_output=True, timeout=120)
            if os.path.exists(norm_tmp) and os.path.getsize(norm_tmp) > 1000:
                os.replace(norm_tmp, audio)
                print(f"[Loudnorm] Ses -14 LUFS normalize edildi")
        except Exception as _ne:
            print(f"[Loudnorm] {_ne}")

        # 2) Image
        _update(f"Generating {style} Art...")
        ig  = ImageGenerator(replicate_key)
        img = os.path.join(VIDEOS_DIR, f"image_{task_id}.jpg")
        category = task.get('category', normalize_category(genre))
        _cat = category.lower()
        # Genre'a özel görsel prompt
        if '80s' in _cat or 'retro' in _cat:
            portrait_prompt = (
                "80s retro style portrait, beautiful woman, big voluminous hair, neon lights, "
                "VHS aesthetic, synthwave vibes, cassette tape era, warm neon glow, "
                "cinematic photography, bokeh background, photorealistic"
            )
        elif 'cyberpunk' in _cat or 'synthwave' in _cat:
            portrait_prompt = (
                "cyberpunk neon portrait, beautiful woman, futuristic city lights, "
                "dark atmosphere, glowing neon accents, digital art, photorealistic"
            )
        elif 'jazz' in _cat:
            portrait_prompt = (
                "jazz club portrait, beautiful woman, warm atmospheric lighting, "
                "vintage bar background, elegant mood, cinematic photography, photorealistic"
            )
        elif 'lofi' in _cat:
            portrait_prompt = (
                "lofi aesthetic portrait, beautiful woman, cozy room, warm lamp light, "
                "rainy window, soft bokeh, anime-inspired, photorealistic"
            )
        elif 'classical' in _cat or 'piano' in _cat or 'cinematic' in _cat:
            portrait_prompt = (
                "classical music portrait, beautiful woman, elegant, grand piano background, "
                "dramatic lighting, cinematic photography, bokeh, photorealistic"
            )
        elif 'afro' in _cat or 'house' in _cat:
            portrait_prompt = (
                "afro house music portrait, beautiful woman, warm sunset colors, "
                "african inspired aesthetic, vibrant atmosphere, bokeh, photorealistic"
            )
        else:
            portrait_prompt = (
                f"{genre}, beautiful woman portrait, close-up face, "
                f"atmospheric {_cat} music mood, cinematic photography, "
                f"bokeh background, editorial style, photorealistic"
            )
        result, image_url = ig.generate_image(portrait_prompt, img, style=style)
        if not result or not os.path.exists(img):
            _update("Error: Image generation failed")
            return
        with _tasks_lock:
            task["image_url"] = image_url
            save_tasks(current_tasks)

        # 3) Video
        _update("Rendering Video...")
        ve       = VideoEngine()
        out_file = f"video_{task_id}.mp4"
        out_path = os.path.join(VIDEOS_DIR, out_file)
        ve.create_video(audio, img, genre=genre, output_path=out_path)
        if not os.path.exists(out_path):
            _update("Error: Video render failed")
            return
        with _tasks_lock:
            task["file"] = out_file
            stats["total_videos"] += 1

        # 4) Upload — channel_slug belirtilmişse o kanalı, yoksa default kanalı kontrol et
        print(f"[Upload] channel_slug={channel_slug!r}  is_connected={is_connected(channel_slug)}")
        if auto_upload and is_connected(channel_slug):
            _update("Uploading to YouTube...")
            privacy = os.getenv('UPLOAD_PRIVACY', 'public')
            title, desc, tags = generate_seo_metadata(genre, style, image_url=image_url,
                                                       music_prompt=task.get("music_prompt"))
            # Thumbnail text overlay — category name büyük & styled
            try:
                ig_tmp = ImageGenerator(replicate_key)
                cat_label = task.get('category') or normalize_category(genre)
                ig_tmp.add_thumbnail_overlay(img, cat_label)
            except Exception as oe:
                print(f"[Overlay] {oe}")
            vid_id = upload_video(out_path, title, desc, tags, privacy=privacy, channel_slug=channel_slug)
            if vid_id:
                set_thumbnail(vid_id, img, channel_slug=channel_slug)
                yt_url = f"https://youtube.com/watch?v={vid_id}"
                with _tasks_lock:
                    task["yt_url"] = yt_url
                _update("YouTube: Uploaded")
                notify_uploaded(title, yt_url, genre)

                # Playlist'e ekle
                try:
                    pl_id = get_or_create_playlist(genre, channel_slug)
                    if pl_id:
                        add_video_to_playlist(vid_id, pl_id, channel_slug)
                except Exception as pe:
                    print(f"[Playlist] {pe}")

                # 5) Shorts (60 sn kesit)
                try:
                    _update("Creating Shorts...")
                    shorts_file = f"shorts_{task_id}.mp4"
                    shorts_path = os.path.join(VIDEOS_DIR, shorts_file)
                    ve2 = VideoEngine()
                    if ve2.create_shorts(out_path, shorts_path, duration=60):
                        shorts_title = f"#Shorts {title[:80]}"
                        shorts_id = upload_video(shorts_path, shorts_title, desc, tags, privacy=privacy, channel_slug=channel_slug)
                        if shorts_id:
                            set_thumbnail(shorts_id, img, channel_slug=channel_slug)
                            shorts_url = f"https://youtube.com/watch?v={shorts_id}"
                            with _tasks_lock:
                                task["shorts_url"] = shorts_url
                            notify_shorts_uploaded(shorts_title, shorts_url)
                except Exception as se:
                    print(f"[Shorts] Hata: {se}")

                _update("YouTube: Uploaded")
            else:
                notify_error(genre, "Upload failed")
                _update("Render OK, Upload Failed")
        else:
            _update("Success")

    except Exception as e:
        task["status"] = f"Error: {str(e)[:60]}"
        with _tasks_lock:
            save_tasks(current_tasks)
        traceback.print_exc()

def _retry_flow(task, genre, style, channel_slug=None):
    """Retry helper — reuses existing task dict instead of appending new one."""
    def _update(status):
        task["status"] = status
        with _tasks_lock:
            save_tasks(current_tasks)

    task_id = task["id"]

    try:
        if not HAS_MODULES:
            _update("Error: Server modules not loaded"); return

        kie_key       = os.getenv('KIE_API_KEY')
        replicate_key = os.getenv('REPLICATE_API_TOKEN')
        if not kie_key or not replicate_key:
            _update("Error: API Keys Missing"); return

        # music_params tam dict → retry'da style/title/negativeTags korunur
        mp = task.get("music_params") or _build_music_prompt(genre, style)
        audio = os.path.join(VIDEOS_DIR, f"music_{task_id}.mp3")
        if os.path.exists(audio):
            _update("Music ready (cached), skipping generation...")
        else:
            _update("Generating Music...")
            mg  = MusicGenerator(kie_key)
            mid = mg.generate_music(mp["prompt"], style=mp.get("style"),
                                    title=mp.get("title"), negative_tags=mp.get("negative_tags"))
            if not mid:
                _update("Error: Music generation failed"); return
            mg.wait_and_download(mid, audio)
            if not os.path.exists(audio):
                _update("Error: Audio file not downloaded"); return

        img = os.path.join(VIDEOS_DIR, f"image_{task_id}.jpg")
        if os.path.exists(img):
            _update("Image ready (cached), skipping generation...")
            image_url = task.get("image_url", "")
        else:
            _update(f"Generating {style} Art...")
            ig  = ImageGenerator(replicate_key)
            category = task.get('category', normalize_category(genre))
            portrait_prompt = (
                f"{genre}, beautiful woman portrait, close-up face, "
                f"atmospheric {category.lower()} music mood, cinematic photography, "
                f"bokeh background, editorial style, photorealistic"
            )
            result, image_url = ig.generate_image(portrait_prompt, img, style=style)
            if not result or not os.path.exists(img):
                _update("Error: Image generation failed"); return
        with _tasks_lock:
            task["image_url"] = image_url
            save_tasks(current_tasks)

        _update("Rendering Video...")
        ve       = VideoEngine()
        out_file = f"video_{task_id}.mp4"
        out_path = os.path.join(VIDEOS_DIR, out_file)
        ve.create_video(audio, img, genre=genre, output_path=out_path)
        if not os.path.exists(out_path):
            _update("Error: Video render failed"); return
        with _tasks_lock:
            task["file"] = out_file
            stats["total_videos"] += 1

        print(f"[Retry/Upload] channel_slug={channel_slug!r}  is_connected={is_connected(channel_slug)}")
        if is_connected(channel_slug):
            _update("Uploading to YouTube...")
            privacy = os.getenv('UPLOAD_PRIVACY', 'public')
            title, desc, tags = generate_seo_metadata(genre, style, image_url=image_url,
                                                       music_prompt=task.get("music_prompt"))
            vid_id = upload_video(out_path, title, desc, tags, privacy=privacy, channel_slug=channel_slug)
            if vid_id:
                set_thumbnail(vid_id, img, channel_slug=channel_slug)
                yt_url = f"https://youtube.com/watch?v={vid_id}"
                with _tasks_lock:
                    task["yt_url"] = yt_url
                _update("YouTube: Uploaded")
                notify_uploaded(title, yt_url, genre)
            else:
                notify_error(genre, "Upload failed")
                _update("Render OK, Upload Failed")
        else:
            _update("Success")

    except Exception as e:
        task["status"] = f"Error: {str(e)[:60]}"
        with _tasks_lock:
            save_tasks(current_tasks)
        traceback.print_exc()


# ── Login / Logout ─────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(request.args.get('next', '/'))
        error = 'Şifre yanlış.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ── Pages ─────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    yt_ch = safe_get_yt_channel()
    with _tasks_lock:
        tasks_snap = list(current_tasks)
    return render_template('index.html', active='dashboard',
                           channels=load_channels(), stats=stats,
                           tasks=tasks_snap, yt_connected=is_connected(), yt_channel=yt_ch)

@app.route('/channels')
@login_required
def channels_page():
    return render_template('channels.html', active='channels',
                           channels=load_channels(),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())


@app.route('/api/channels/default/<slug>', methods=['POST'])
def api_channel_default(slug):
    try:
        set_default_channel(slug)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/channels/remove/<slug>', methods=['POST'])
def api_channel_remove(slug):
    try:
        ch = remove_channel(slug)
        if ch:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Kanal bulunamadi"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/channels')
def api_channels():
    return jsonify({"channels": load_channels()})

@app.route('/library')
@login_required
def library():
    tracks = [file_info(f) for f in get_file_list('.mp3')]
    return render_template('library.html', active='library',
                           tracks=tracks, yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/tasks')
@login_required
def tasks_page():
    with _tasks_lock:
        tasks_snap = list(current_tasks)
    return render_template('tasks.html', active='tasks',
                           tasks=tasks_snap, yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/stream')
@login_required
def stream_page():
    prefill   = request.args.get('video', '')
    videos    = get_file_list('.mp4')
    tags      = get_tags_map()
    sk_store  = load_stream_keys()
    channels  = load_channels()
    # Seçili kanalın (ilk kanal) status'unu göster
    first_slug = channels[0]['slug'] if channels else 'default'
    return render_template('stream.html', active='stream',
                           videos=videos, prefill=prefill,
                           tags=tags, sk_store=sk_store,
                           channels=channels,
                           stream_status=stream_status(first_slug), ffmpeg_ok=is_ffmpeg_installed(),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    global MAX_CONCURRENT_JOBS, ADMIN_PASSWORD
    saved = False
    if request.method == 'POST':
        # Şifre değiştirme
        new_pw = request.form.get('admin_password', '').strip()
        if new_pw and len(new_pw) >= 4:
            ADMIN_PASSWORD = new_pw
            os.environ['ADMIN_PASSWORD'] = new_pw
            try: set_key(ENV_FILE, 'ADMIN_PASSWORD', new_pw)
            except Exception: pass
        kie_key  = request.form.get('kie_key',  '').strip()
        rep_key  = request.form.get('replicate_key', '').strip()
        privacy  = request.form.get('upload_privacy', 'private')
        max_jobs = request.form.get('max_jobs', '').strip()
        if max_jobs in ('1', '2'):
            MAX_CONCURRENT_JOBS = int(max_jobs)
            os.environ['MAX_CONCURRENT_JOBS'] = max_jobs
            try: set_key(ENV_FILE, 'MAX_CONCURRENT_JOBS', max_jobs)
            except Exception: pass
        if kie_key:
            os.environ['KIE_API_KEY'] = kie_key
            try: set_key(ENV_FILE, 'KIE_API_KEY', kie_key)
            except Exception: pass
        if rep_key:
            os.environ['REPLICATE_API_TOKEN'] = rep_key
            try: set_key(ENV_FILE, 'REPLICATE_API_TOKEN', rep_key)
            except Exception: pass
        if privacy in ('private', 'unlisted', 'public'):
            os.environ['UPLOAD_PRIVACY'] = privacy
            try: set_key(ENV_FILE, 'UPLOAD_PRIVACY', privacy)
            except Exception: pass
        tg_token   = request.form.get('telegram_token',   '').strip()
        tg_chat_id = request.form.get('telegram_chat_id', '').strip()
        if tg_token:
            os.environ['TELEGRAM_TOKEN'] = tg_token
            try: set_key(ENV_FILE, 'TELEGRAM_TOKEN', tg_token)
            except Exception: pass
        if tg_chat_id:
            os.environ['TELEGRAM_CHAT_ID'] = tg_chat_id
            try: set_key(ENV_FILE, 'TELEGRAM_CHAT_ID', tg_chat_id)
            except Exception: pass
        saved = True
    return render_template('settings.html', active='settings', saved=saved,
                           kie_key=os.getenv('KIE_API_KEY', ''),
                           replicate_key=os.getenv('REPLICATE_API_TOKEN', ''),
                           upload_privacy=os.getenv('UPLOAD_PRIVACY', 'public'),
                           max_jobs=os.getenv('MAX_CONCURRENT_JOBS', '1'),
                           telegram_token=os.getenv('TELEGRAM_TOKEN', ''),
                           telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

# ── API ───────────────────────────────────────────────
@app.route('/api/generate', methods=['POST'])
def api_generate():
    d = request.json or {}
    genre = d.get('genre', '').strip()
    if not genre:
        return jsonify({"status": "error", "message": "Genre/vibe is required"}), 400

    # CPU guard — don't start a new render when system is overloaded
    cpu = _get_cpu_percent()
    if cpu > 85:
        return jsonify({"status": "error",
                        "message": f"System CPU at {cpu:.0f}% — too high to start a new render. Try again shortly."}), 503

    # task_ref henüz oluşturulmadı, queue içinde ilk adımda oluşacak
    # Dummy ref ile kuyruğa ekle
    dummy = {}
    _enqueue_flow(
        dummy,
        run_automation_flow,
        genre, d.get('style', 'Cinematic'), d.get('lyrics', True), True,
        channel_slug=d.get('channel_slug'),
        min_duration=int(d.get('min_duration', 0)),
    )
    q_size = _prod_queue.qsize()
    msg = f"'{genre}' kuyruğa eklendi!" if q_size > 0 else f"'{genre}' üretimi başladı!"
    return jsonify({"status": "success", "message": msg, "queue_position": q_size})

@app.route('/api/status')
def api_status():
    with _tasks_lock:
        tasks_snap = list(current_tasks)
    limit = request.args.get('limit', type=int)
    out   = tasks_snap[-limit:] if (limit and limit > 0) else tasks_snap
    q = get_quota_usage()
    enriched_stats = dict(stats)
    remaining_uploads = max(0, (q["limit"] - q["used"]) // 1600)
    enriched_stats["credits_used"] = f"{remaining_uploads} uploads left"
    enriched_stats["quota_used"] = q["used"]
    enriched_stats["quota_limit"] = q["limit"]
    return jsonify({"tasks": out, "stats": enriched_stats, "yt_connected": is_connected()})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    d        = request.json or {}
    filename = d.get('file')
    if not filename:
        return jsonify({"error": "No file specified"}), 400
    if not is_connected():
        return jsonify({"error": "YouTube account not connected"}), 401
    path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found on server"}), 404

    with _tasks_lock:
        task_ref = next((t for t in current_tasks if t.get('file') == filename), {})

    genre        = d.get('genre')  or task_ref.get('genre')     or 'AI Music'
    style        = d.get('style')  or task_ref.get('style')     or 'Cinematic'
    image_url    = task_ref.get('image_url')
    task_id      = task_ref.get('id')
    channel_slug = d.get('channel_slug') or task_ref.get('channel_slug') or None
    privacy      = os.getenv('UPLOAD_PRIVACY', 'private')

    title, desc, tags = generate_seo_metadata(genre, style, image_url=image_url)
    vid_id = upload_video(path, title, desc, tags, privacy=privacy, channel_slug=channel_slug)
    if vid_id:
        # Set thumbnail from local image file
        if task_id:
            img_path = os.path.join(VIDEOS_DIR, f"image_{task_id}.jpg")
            set_thumbnail(vid_id, img_path)
        with _tasks_lock:
            for t in current_tasks:
                if t.get('file') == filename:
                    t['yt_url'] = f"https://youtube.com/watch?v={vid_id}"
                    t['status'] = "YouTube: Uploaded"
            save_tasks(current_tasks)
        return jsonify({"message": "Uploaded!", "url": f"https://youtube.com/watch?v={vid_id}"})
    return jsonify({"error": "Upload failed"}), 500

@app.route('/api/retry/<int:task_id>', methods=['POST'])
def api_retry(task_id):
    with _tasks_lock:
        task = next((t for t in current_tasks if t.get('id') == task_id), None)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if 'Error' not in task.get('status', '') and 'Failed' not in task.get('status', ''):
        return jsonify({"error": "Task is not in a failed state"}), 400
    genre        = task.get('genre', 'Lofi Chill')
    style        = task.get('style', 'Cinematic')
    channel_slug = task.get('channel_slug') or None   # "" → None (default kanal)
    with _tasks_lock:
        task['status'] = 'Retrying...'
        task['file']   = None
        task['yt_url'] = None
        save_tasks(current_tasks)
    t = threading.Thread(target=_retry_flow, args=(task, genre, style), kwargs={'channel_slug': channel_slug}, daemon=True)
    t.start()
    return jsonify({"message": "Retry started!"})

@app.route('/api/tasks/<int:task_id>/category', methods=['POST'])
def api_set_category(task_id):
    data = request.json or {}
    new_cat = (data.get('category') or '').strip()
    if not new_cat:
        return jsonify({"error": "category required"}), 400
    with _tasks_lock:
        task = next((t for t in current_tasks if t.get('id') == task_id), None)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        task['category'] = new_cat
        save_tasks(current_tasks)
    return jsonify({"ok": True, "category": new_cat})

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    d         = request.json or {}
    keep_days = int(d.get('keep_days', 7))
    cutoff    = time.time() - (keep_days * 86400)
    deleted   = []
    errors    = []
    for fname in os.listdir(VIDEOS_DIR):
        if not fname.endswith(('.mp4', '.mp3', '.jpg')):
            continue
        fpath = os.path.join(VIDEOS_DIR, fname)
        try:
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                deleted.append(fname)
        except Exception as e:
            errors.append(str(e))
    # Remove orphaned task file refs
    with _tasks_lock:
        for t in current_tasks:
            if t.get('file') and t['file'] in deleted:
                t['file'] = None
        save_tasks(current_tasks)
    return jsonify({"deleted": len(deleted), "files": deleted, "errors": errors})

@app.route('/api/stream/start', methods=['POST'])
def api_stream_start():
    d            = request.json or {}
    stream_key   = d.get('stream_key', '').strip()
    mode         = d.get('mode', 'single')
    shuffle      = d.get('shuffle', False)
    bg_video     = d.get('bg_video', '').strip()
    channel_slug = d.get('channel_slug', 'default').strip() or 'default'

    if not stream_key:
        return jsonify({"error": "Stream key required"}), 400

    sk_store = load_stream_keys()
    tag_key  = d.get('tag', channel_slug)
    sk_store[tag_key]      = stream_key
    sk_store[channel_slug] = stream_key
    save_stream_keys(sk_store)

    if mode == 'tag':
        tag      = d.get('tag', '').strip()
        tags_map = get_tags_map()
        paths    = tags_map.get(tag, [])
        if not paths:
            return jsonify({"error": f"'{tag}' etiketinde video bulunamadi"}), 404
        ok, msg = start_stream_playlist(stream_key, paths, tag=tag,
                                        shuffle=shuffle, bg_video_url=bg_video,
                                        channel_slug=channel_slug)
    else:
        video = d.get('video', '').strip()
        if not video:
            return jsonify({"error": "Video secilmedi"}), 400
        video_path = os.path.join(VIDEOS_DIR, video)
        if not os.path.exists(video_path):
            return jsonify({"error": "Video dosyasi bulunamadi"}), 404
        ok, msg = start_stream_playlist(stream_key, [video_path], shuffle=False,
                                        bg_video_url=bg_video, channel_slug=channel_slug)

    if ok:
        stats["active_streams"] = len([s for s in get_all_statuses() if s.get("active")])
    return jsonify({"message": msg, "ok": ok})


@app.route('/api/stream/bg-video', methods=['POST'])
def api_stream_bg_video():
    """Arka plan video URL'sini test et / önceden indir."""
    d   = request.json or {}
    url = d.get('url', '').strip()
    if not url:
        return jsonify({"error": "URL gerekli"}), 400
    ok, result = download_bg_video(url)
    if ok:
        size_mb = round(os.path.getsize(result) / 1024 / 1024, 1)
        return jsonify({"ok": True, "message": f"Video hazır ({size_mb} MB)"})
    return jsonify({"ok": False, "message": result})


@app.route('/api/stream/local-bg', methods=['POST'])
def api_stream_local_bg():
    """
    Kullanıcının localindeki dosyayı paramiko SFTP ile VPS'e kopyalar.
    Flask sunucusu VPS'in kendisiyse direkt kopyalar.
    """
    import shutil
    d    = request.json or {}
    path = d.get('path', '').strip()
    if not path:
        return jsonify({"ok": False, "message": "Dosya yolu gerekli"}), 400

    bg_path = '/tmp/yt_stream_bg.mp4'

    # VPS'de mi? Localden kopyala
    if os.path.exists(path):
        try:
            shutil.copy2(path, bg_path)
            size_mb = round(os.path.getsize(bg_path) / 1024 / 1024, 1)
            # ffprobe doğrula
            import subprocess as sp
            probe = sp.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                           '-show_entries', 'stream=width', '-of', 'default=noprint_wrappers=1',
                           bg_path], capture_output=True, timeout=10)
            if probe.returncode != 0:
                os.remove(bg_path)
                return jsonify({"ok": False, "message": "Geçersiz video dosyası"}), 400
            return jsonify({"ok": True, "message": f"Kopyalandı ({size_mb} MB)"})
        except Exception as e:
            return jsonify({"ok": False, "message": str(e)}), 500
    else:
        return jsonify({"ok": False, "message": f"Dosya bulunamadı: {path}"}), 404


@app.route('/api/stream/upload-bg', methods=['POST'])
def api_stream_upload_bg():
    """Localdan arka plan video yükle — VPS'e /tmp/yt_stream_bg.mp4 olarak kaydeder."""
    if 'file' not in request.files:
        return jsonify({"ok": False, "message": "Dosya bulunamadı"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"ok": False, "message": "Geçersiz dosya"}), 400
    try:
        bg_path = '/tmp/yt_stream_bg.mp4'
        f.save(bg_path)
        size_mb = round(os.path.getsize(bg_path) / 1024 / 1024, 1)

        # ffprobe ile doğrula — bozuk dosya olmasın
        import subprocess as sp
        probe = sp.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height,duration',
             '-of', 'default=noprint_wrappers=1', bg_path],
            capture_output=True, timeout=15
        )
        if probe.returncode != 0:
            os.remove(bg_path)
            probe_err = probe.stderr.decode('utf-8', errors='replace')[:200]
            return jsonify({"ok": False, "message": f"Gecersiz video dosyasi: {probe_err}"}), 400

        return jsonify({"ok": True, "message": "Yuklendi", "size_mb": size_mb})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route('/api/tags')
def api_tags():
    tags = get_tags_map()
    return jsonify({k: len(v) for k, v in tags.items()})

@app.route('/api/stream/autokey', methods=['POST'])
def api_stream_autokey():
    """YouTube API üzerinden stream key'i otomatik alır veya oluşturur."""
    d            = request.json or {}
    channel_slug = d.get('channel_slug', 'default').strip() or 'default'
    title        = d.get('title', 'AI Music 24/7 Live Stream')
    if not HAS_MODULES:
        return jsonify({"error": "Modules not loaded"}), 503
    if not is_connected(channel_slug):
        return jsonify({"error": "Bu kanal YouTube'a bağlı değil"}), 400
    key, broadcast_id, err = get_or_create_live_stream_key(title, channel_slug)
    if err:
        # Canlı yayın aktif değil — kullanıcıya özel mesaj ver
        if 'liveStreamingNotEnabled' in str(err) or 'not enabled for live streaming' in str(err):
            return jsonify({
                "error": "not_enabled",
                "message": "Bu YouTube kanalında canlı yayın özelliği kapalı.",
                "help": "youtube.com/features adresine gidip 'Canlı Yayın'ı etkinleştir (24 saat sürebilir). Etkinleştirince stream key'i YouTube Studio → Go Live → Ayarlar'dan manuel olarak gir."
            }), 403
        return jsonify({"error": err}), 500
    # Anahtarı kaydet (sk_store)
    sk_store = load_stream_keys()
    sk_store[channel_slug] = key
    save_stream_keys(sk_store)
    return jsonify({"ok": True, "key": key, "broadcast_id": broadcast_id})


@app.route('/api/stream/stop', methods=['POST'])
def api_stream_stop():
    d            = request.json or {}
    channel_slug = d.get('channel_slug', 'default').strip() or 'default'
    ok, msg = stop_stream(channel_slug)
    if ok:
        stats["active_streams"] = len([s for s in get_all_statuses() if s.get("active")])
    return jsonify({"message": msg, "ok": ok})

@app.route('/api/stream/status')
def api_stream_status():
    channel_slug = request.args.get('channel_slug')
    if channel_slug:
        return jsonify(stream_status(channel_slug))
    # Tüm kanallar
    return jsonify({"streams": get_all_statuses()})

@app.route('/api/stream/all')
def api_stream_all():
    return jsonify({"streams": get_all_statuses()})

@app.route('/api/stream/title', methods=['POST'])
def api_stream_title():
    data  = request.json or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    channel_slug = data.get('channel_slug') or None
    ok, msg = update_live_broadcast_title(title, channel_slug=channel_slug)
    return jsonify({"ok": ok, "message": msg})

# ── YouTube Auth ──────────────────────────────────────
@app.route('/login/youtube')
def login_youtube():
    secrets_file = os.environ.get('CLIENT_SECRETS_FILE', os.path.join(_base_dir, 'client_secrets.json'))
    if not os.path.exists(secrets_file):
        return jsonify({"error": "client_secrets.json not found."}), 400
    try:
        auth_url, state, _ = get_auth_url()
        session['yt_state'] = state
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": f"OAuth setup failed: {str(e)}"}), 500

@app.route('/callback/youtube', methods=['GET', 'POST'])
def callback_youtube():
    code = request.args.get('code')
    if not code:
        return "Error: No auth code received", 400
    try:
        exchange_code(code, request.args.get('state'))
    except Exception as e:
        return f"Error during token exchange: {e}", 500
    return redirect('/')

@app.route('/logout/youtube')
def logout_youtube():
    try:
        token_file = os.environ.get('TOKEN_FILE', os.path.join(_base_dir, 'token.pickle'))
        if os.path.exists(token_file):
            os.remove(token_file)
    except Exception:
        pass
    return redirect('/')

# ── Files ─────────────────────────────────────────────
@app.route('/download/<filename>')
def download_file(filename):
    # Path traversal koruması
    safe = os.path.basename(filename)
    if not safe or safe != filename:
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(VIDEOS_DIR, safe, as_attachment=True)

@app.route('/outputs/<filename>')
def serve_output(filename):
    safe = os.path.basename(filename)
    return send_from_directory(VIDEOS_DIR, safe)

# ── Resource helpers ──────────────────────────────────
def _get_cpu_percent():
    try:
        import psutil
        return psutil.cpu_percent(interval=0.5)
    except ImportError:
        try:
            result = subprocess.check_output(['cat', '/proc/loadavg'], timeout=2).decode()
            load1 = float(result.split()[0])
            return min(100.0, load1 / (os.cpu_count() or 1) * 100.0)
        except Exception:
            return 0.0

def _get_ram_percent():
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        try:
            lines = open('/proc/meminfo').readlines()
            info = {l.split(':')[0]: int(l.split(':')[1].strip().split()[0]) for l in lines if ':' in l}
            total = info.get('MemTotal', 1)
            avail = info.get('MemAvailable', total)
            return round((1 - avail / total) * 100, 1)
        except Exception:
            return 0.0

@app.route('/api/system')
def api_system():
    cpu = _get_cpu_percent()
    ram = _get_ram_percent()
    with _active_lock:
        active = _active_jobs
    q = get_quota_usage()
    return jsonify({
        "cpu": round(cpu, 1),
        "ram": round(ram, 1),
        "active_jobs": active,
        "max_jobs": MAX_CONCURRENT_JOBS,
        "warning": cpu > 80 or ram > 85,
        "quota_used": q["used"],
        "quota_limit": q["limit"],
        "quota_pct": round(q["used"] / q["limit"] * 100, 1) if q["limit"] else 0,
    })

@app.route('/api/quota')
def api_quota():
    return jsonify(get_quota_usage())

# ── VPS Monitor ───────────────────────────────────────
def get_vps_stats():
    def _sh(cmd, default="N/A"):
        try:
            # shell=True yerine bash -c ile çalıştır (injection riski azalt)
            return subprocess.check_output(
                ['bash', '-c', cmd], timeout=5
            ).decode(errors='replace').strip()
        except Exception:
            return default

    cpu      = _sh("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    mem      = _sh("free -m | awk 'NR==2{printf \"%s/%s MB (%.0f%%)\", $3,$2,$3*100/$2}'")
    disk     = _sh("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'")
    uptime   = _sh("uptime -p")
    logs     = _sh("tail -20 /root/Yt/output.log 2>/dev/null || echo 'Log yok'", "Log okunamadi")
    nginx    = _sh("systemctl is-active nginx 2>/dev/null", "unknown")
    out_size = _sh("du -sh /root/Yt/outputs/ 2>/dev/null | cut -f1", "0")
    out_count = _sh("ls /root/Yt/outputs/*.mp4 2>/dev/null | wc -l", "0")
    try:
        proc = _sh("ps aux | grep 'python3 app.py' | grep -v grep | wc -l", "0")
        app_running = int(proc) > 0
    except Exception:
        app_running = False

    # Disk doluluk % — uyarı için
    disk_pct = 0
    try:
        disk_pct = int(_sh("df / | awk 'NR==2{print $5}' | tr -d '%'", "0"))
    except Exception:
        pass

    return {
        "cpu": cpu, "ram": mem, "disk": disk, "uptime": uptime,
        "app_running": app_running, "nginx": nginx, "logs": logs,
        "output_size": out_size, "output_videos": out_count,
        "yt_connected": is_connected(),
        "kie_set": bool(os.getenv('KIE_API_KEY')),
        "replicate_set": bool(os.getenv('REPLICATE_API_TOKEN')),
        "modules_ok": HAS_MODULES,
        "disk_pct": disk_pct,
        "disk_warning": disk_pct >= 85,
    }

@app.route('/monitor')
@login_required
def monitor():
    vps = get_vps_stats()
    return render_template('monitor.html', active='monitor',
                           vps=vps, yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/api/monitor')
def api_monitor():
    return jsonify(get_vps_stats())

@app.route('/api/analytics')
def api_analytics():
    try:
        from analytics import get_channel_analytics, get_api_status
        slug = request.args.get('slug') or None
        days = int(request.args.get('days', 28))
        yt   = get_channel_analytics(slug, days)
        api  = get_api_status()
        return jsonify({"youtube": yt, "api": api})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backup/stats')
def api_backup_stats():
    try:
        from backup import get_backup_stats
        return jsonify(get_backup_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backup/run', methods=['POST'])
def api_backup_run():
    try:
        from backup import run_daily_backup
        result = run_daily_backup()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trending')
def api_trending():
    try:
        from analytics import get_trending_music_topics
        topics = get_trending_music_topics(limit=10)
        return jsonify({"topics": topics})
    except Exception as e:
        return jsonify({"topics": [], "error": str(e)})

@app.route('/analytics')
@login_required
def analytics_page():
    return render_template('analytics.html', active='analytics',
                           channels=load_channels(),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

# ── Schedules ─────────────────────────────────────────
@app.route('/schedules')
@login_required
def schedules_page():
    scheds = list_schedules() if HAS_SCHEDULER else []
    return render_template('schedules.html', active='schedules',
                           schedules=scheds, channels=load_channels(),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/api/schedules', methods=['GET'])
def api_schedules_list():
    return jsonify(list_schedules() if HAS_SCHEDULER else [])

@app.route('/api/schedules', methods=['POST'])
def api_schedules_create():
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    s = add_schedule(request.json or {})
    return jsonify(s), 201

@app.route('/api/schedules/<sid>', methods=['PUT'])
def api_schedules_update(sid):
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    s = update_schedule(sid, request.json or {})
    return jsonify(s) if s else (jsonify({"error": "Not found"}), 404)

@app.route('/api/schedules/<sid>', methods=['DELETE'])
def api_schedules_delete(sid):
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    return jsonify({"ok": delete_schedule(sid)})

@app.route('/api/schedules/<sid>/toggle', methods=['POST'])
def api_schedules_toggle(sid):
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    s = toggle_schedule(sid, bool((request.json or {}).get('enabled', True)))
    return jsonify(s) if s else (jsonify({"error": "Not found"}), 404)

@app.route('/api/schedules/<sid>/run_now', methods=['POST'])
def api_schedules_run_now(sid):
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    ok = sched_run_now(sid)
    return jsonify({"message": "Production started!"}) if ok else (jsonify({"error": "Not found"}), 404)

@app.route('/api/schedules/bulk', methods=['POST'])
def api_schedules_bulk():
    """
    Birden fazla kanala aynı anda schedule oluşturur.
    Payload: { genre, style, days_of_week, min_duration,
               channel_slugs: [slug1, slug2, ...],
               time_slots: [{hour:7,minute:0},{hour:19,minute:0}] }
    """
    if not HAS_SCHEDULER:
        return jsonify({"error": "Scheduler not available"}), 503
    d     = request.json or {}
    slugs = d.get('channel_slugs', [''])
    if not slugs:
        slugs = ['']

    # Manuel saat slotları (yeni) veya eski start_hour+vpd hesabı (geriye dönük uyumluluk)
    time_slots = d.get('time_slots')
    if not time_slots:
        vpd        = max(1, int(d.get('videos_per_day', 1)))
        start_hour = int(d.get('time_hour', 18))
        start_min  = int(d.get('time_minute', 0))
        interval   = 24 // vpd
        time_slots = [{'hour': (start_hour + i * interval) % 24, 'minute': start_min}
                      for i in range(vpd)]

    channels_list = load_channels()
    created = []
    for slug in slugs:
        ch_name = next((c['name'] for c in channels_list if c['slug'] == slug), 'Default')
        for slot in time_slots:
            hour   = int(slot.get('hour', 12))
            minute = int(slot.get('minute', 0))
            suffix = f" [{hour:02d}:{minute:02d}]" if len(time_slots) > 1 else ""
            sched_data = {
                'name':           f"{d.get('genre','Video')[:28]} — {ch_name}{suffix}",
                'genre':          d.get('genre', 'Lofi Chill'),
                'style':          d.get('style', 'Cinematic'),
                'days_of_week':   d.get('days_of_week', '*'),
                'time_hour':      hour,
                'time_minute':    minute,
                'min_duration':   int(d.get('min_duration', 0)),
                'channel_slug':   slug,
                'lyrics_enabled': False,
                'enabled':        True,
            }
            sched = add_schedule(sched_data)
            created.append(sched)
    return jsonify({"ok": True, "created": len(created), "schedules": created})

# ── Error Handlers ────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    with _tasks_lock:
        tasks_snap = list(current_tasks)
    return render_template('index.html', active='dashboard',
                           channels=load_channels(), stats=stats,
                           tasks=tasks_snap, yt_connected=is_connected(),
                           yt_channel=safe_get_yt_channel()), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "details": str(e)}), 500

# ── App Initialization (Gunicorn + direct run için) ───
_startup_done = False

def _startup():
    """Scheduler + arka plan işleri başlatır. Hem Gunicorn hem direct run için."""
    global _startup_done
    if _startup_done:
        return
    _startup_done = True

    print("\n MASTER AUTO V12 - ALLONE AI")
    print(f"  Modules:             {'OK' if HAS_MODULES else 'MISSING'}")
    print(f"  KIE_API_KEY:         {'Set' if os.getenv('KIE_API_KEY') else 'Missing'}")
    print(f"  REPLICATE_API_TOKEN: {'Set' if os.getenv('REPLICATE_API_TOKEN') else 'Missing'}")
    print(f"  Upload Privacy:      {os.getenv('UPLOAD_PRIVACY', 'private')}")
    print(f"  YouTube:             {'Connected' if is_connected() else 'Not connected'}")
    print(f"  FFmpeg:              {'Installed' if is_ffmpeg_installed() else 'Not found'}")
    if HAS_SCHEDULER:
        def _sched_enqueue(fn, *args):
            _enqueue_flow({}, fn, *args)
        init_scheduler(run_automation_flow, enqueue_fn=_sched_enqueue)
        try:
            from backup import run_daily_backup
            from apscheduler.triggers.cron import CronTrigger
            import pytz
            from apscheduler.schedulers.background import BackgroundScheduler
            _backup_sched = BackgroundScheduler(timezone=pytz.timezone('America/New_York'))
            _backup_sched.add_job(run_daily_backup, CronTrigger(hour=3, minute=0), id='daily_backup', replace_existing=True)

            def _send_weekly_report():
                try:
                    total    = len(current_tasks)
                    uploaded = sum(1 for t in current_tasks if t.get('yt_url'))
                    genres   = list({t.get('name', '').split(' Video')[0].strip()
                                     for t in current_tasks if t.get('name')})
                    notify_weekly_report(total, uploaded, genres)
                except Exception as wre:
                    print(f"  [Weekly report] {wre}")

            def _auto_disk_cleanup():
                try:
                    keep_days = int(os.getenv('AUTO_CLEANUP_DAYS', '14'))
                    cutoff    = time.time() - (keep_days * 86400)
                    deleted   = []
                    for fname in os.listdir(VIDEOS_DIR):
                        if not fname.endswith(('.mp4', '.mp3', '.jpg')):
                            continue
                        fpath = os.path.join(VIDEOS_DIR, fname)
                        try:
                            if os.path.getmtime(fpath) < cutoff:
                                os.remove(fpath)
                                deleted.append(fname)
                        except Exception:
                            pass
                    if deleted:
                        with _tasks_lock:
                            for t in current_tasks:
                                if t.get('file') and t['file'] in deleted:
                                    t['file'] = None
                            save_tasks(current_tasks)
                        print(f"[AutoCleanup] {len(deleted)} dosya silindi ({keep_days}g+ eski)")
                except Exception as ce:
                    print(f"[AutoCleanup] {ce}")

            def _prune_tasks():
                MAX_TASKS = 300
                with _tasks_lock:
                    if len(current_tasks) > MAX_TASKS:
                        keep = current_tasks[-MAX_TASKS:]
                        removed = len(current_tasks) - MAX_TASKS
                        current_tasks.clear()
                        current_tasks.extend(keep)
                        save_tasks(current_tasks)
                        print(f"[TaskPrune] {removed} eski görev temizlendi, {MAX_TASKS} görev kaldı")

            _backup_sched.add_job(_send_weekly_report,  CronTrigger(day_of_week='sun', hour=9, minute=0),  id='weekly_report',    replace_existing=True)
            _backup_sched.add_job(_auto_disk_cleanup,   CronTrigger(hour=4, minute=0),                     id='auto_disk_cleanup', replace_existing=True)
            _backup_sched.add_job(_prune_tasks,         CronTrigger(hour=4, minute=30),                    id='task_prune',        replace_existing=True)
            _backup_sched.start()
            import atexit; atexit.register(lambda: _backup_sched.shutdown(wait=False))
        except Exception as be:
            print(f"  [Backup scheduler] {be}")
        print(f"  Scheduler:           Active (Eastern Time)")
    else:
        print(f"  Scheduler:           Not available")

_startup()   # Gunicorn import ettiğinde de çalışır

# ── Entry Point (direkt python app.py ile çalıştırma) ─
if __name__ == '__main__':
    print("  Starting on port 5000...\n")
    app.run(host='0.0.0.0', port=5000, threaded=True)
