"""
Multi-channel live stream manager.
Her kanal bağımsız StreamSession ile yönetilir.
"""
import subprocess
import os
import threading
import time
import random

# ── Global session registry ────────────────────────────────────────────────────
_sessions      = {}          # slug → StreamSession
_sessions_lock = threading.Lock()

BG_VIDEO_DIR = '/tmp'


# ── Helpers ────────────────────────────────────────────────────────────────────
def _playlist_path(slug: str) -> str:
    return f'/tmp/yt_stream_playlist_{slug}.txt'

def _bg_video_path(slug: str) -> str:
    return f'/tmp/yt_stream_bg_{slug}.mp4'

# Legacy global bg path (upload endpoint için)
BG_VIDEO_PATH = '/tmp/yt_stream_bg.mp4'


def _write_playlist(paths: list, slug: str, repeat: int = 200) -> str:
    pl = _playlist_path(slug)
    with open(pl, 'w') as f:
        for _ in range(repeat):
            for p in paths:
                f.write(f"file '{p}'\n")
    return pl


def _build_ffmpeg_cmd(input_arg: list, rtmp_url: str, bg_video: str = None) -> list:
    # 720p @ 3000k — VPS'de gerçek zamanlı encode için dengeli ayarlar
    # nice kaldırıldı: stream CPU önceliği olmalı, yoksa YouTube buffer uyarısı verir
    base_enc = [
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
        "-b:v", "3000k", "-maxrate", "3500k", "-bufsize", "6000k",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-pix_fmt", "yuv420p", "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-f", "flv", rtmp_url
    ]
    if bg_video and os.path.exists(bg_video):
        return [
            "ffmpeg",
            "-re", "-stream_loop", "-1", "-i", bg_video,
            "-re", "-stream_loop", "-1", *input_arg,
            "-map", "0:v", "-map", "1:a",
            *base_enc
        ]
    else:
        return [
            "ffmpeg",
            "-re", "-stream_loop", "-1", *input_arg,
            *base_enc
        ]


# ── StreamSession ──────────────────────────────────────────────────────────────
class StreamSession:
    """Tek bir kanalın canlı yayın oturumunu yönetir."""

    def __init__(self, slug: str):
        self.slug     = slug
        self.lock     = threading.Lock()
        self.process  = None
        self.monitor_thread = None
        self.stop_requested = False

        # Reconnect parametreleri
        self.last_input_arg = None
        self.last_rtmp_url  = None
        self.last_playlist  = []
        self.last_bg_video  = None

        self.status = self._empty_status()

    def _empty_status(self):
        return {
            "active": False, "reconnecting": False,
            "key": None, "started": None, "start_ts": None,
            "video": None, "tag": None, "playlist": [],
            "mode": "single", "reconnects": 0,
            "data_status": "idle", "healthy": False,
            "bg_video": None, "elapsed": "00:00:00",
            "slug": self.slug,
        }

    def _spawn_ffmpeg(self):
        """FFmpeg'i (yeniden) başlatır."""
        if self.last_playlist and len(self.last_playlist) > 1:
            pl = _write_playlist(self.last_playlist, self.slug)
            self.last_input_arg = ["-f", "concat", "-safe", "0", "-i", pl]
        cmd = _build_ffmpeg_cmd(self.last_input_arg, self.last_rtmp_url, self.last_bg_video)
        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with self.lock:
            self.status["active"]      = True
            self.status["data_status"] = "sending"
            self.status["healthy"]     = True
        print(f"[Stream:{self.slug}] FFmpeg started — PID {self.process.pid}")

    def _monitor(self):
        """FFmpeg stderr izler, process ölünce yeniden bağlanır."""
        import select as _select
        while True:
            if self.stop_requested:
                break
            proc = self.process
            if proc is None:
                break

            # Non-blocking stderr oku
            line = b""
            try:
                try:
                    rlist, _, _ = _select.select([proc.stderr], [], [], 1.0)
                    if rlist:
                        line = proc.stderr.readline()
                except (ValueError, OSError):
                    line = proc.stderr.readline() if proc.poll() is None else b""
            except Exception as e:
                print(f"[Monitor:{self.slug}] stderr error: {e}")
                break

            if line:
                txt = line.decode("utf-8", errors="replace")
                with self.lock:
                    if "frame=" in txt or "size=" in txt:
                        self.status["data_status"] = "sending"
                        self.status["healthy"]     = True
                    elif "error" in txt.lower() or "failed" in txt.lower():
                        self.status["data_status"] = "error"
                        self.status["healthy"]     = False

            # Process öldü mü?
            if proc.poll() is not None:
                if self.stop_requested:
                    break
                with self.lock:
                    self.status["healthy"]     = False
                    self.status["data_status"] = "idle"

                if self.last_rtmp_url and self.last_input_arg:
                    rc = self.status["reconnects"] + 1
                    print(f"[Stream:{self.slug}] Process öldü — reconnect #{rc}")
                    with self.lock:
                        self.status["active"]       = True
                        self.status["reconnecting"] = True
                    time.sleep(4)
                    if self.stop_requested:
                        break
                    with self.lock:
                        self.status["reconnects"] += 1
                    self._spawn_ffmpeg()
                    with self.lock:
                        self.status["reconnecting"] = False
                else:
                    with self.lock:
                        self.status["active"] = False
                    break

            time.sleep(0.1)

    def start(self, stream_key: str, video_paths: list,
              tag: str = "", shuffle: bool = False, bg_video_url: str = ""):
        with self.lock:
            if self.process and self.process.poll() is None:
                return False, "Bu kanal zaten yayında."

        existing = [p for p in video_paths if os.path.exists(p)]
        if not existing:
            return False, "Hiçbir video dosyası bulunamadı."

        if shuffle:
            random.shuffle(existing)

        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"

        if len(existing) == 1:
            input_arg = ["-i", existing[0]]
            display   = os.path.basename(existing[0])
        else:
            pl        = _write_playlist(existing, self.slug)
            input_arg = ["-f", "concat", "-safe", "0", "-i", pl]
            display   = f"{len(existing)} video"

        # Arka plan video
        bg_path = None
        bg_label = None
        slug_bg = _bg_video_path(self.slug)

        if bg_video_url and bg_video_url.strip():
            ok, result = download_bg_video(bg_video_url.strip(), dest=slug_bg)
            if ok:
                bg_path  = result
                bg_label = bg_video_url.strip()
            else:
                print(f"[Stream:{self.slug}] BG video indirilemedi: {result}")
        elif os.path.exists(slug_bg) and os.path.getsize(slug_bg) > 10000:
            bg_path  = slug_bg
            bg_label = "Yerel dosya"
        elif os.path.exists(BG_VIDEO_PATH) and os.path.getsize(BG_VIDEO_PATH) > 10000:
            # Paylaşılan global bg video (upload ile yüklenen)
            bg_path  = BG_VIDEO_PATH
            bg_label = "Yerel dosya"

        self.stop_requested  = False
        self.last_input_arg  = input_arg
        self.last_rtmp_url   = rtmp_url
        self.last_playlist   = existing
        self.last_bg_video   = bg_path

        now = time.time()
        with self.lock:
            self.status = {
                "active": True, "reconnecting": False,
                "key":     stream_key[:4] + "****" + stream_key[-4:] if len(stream_key) > 8 else "****",
                "started": time.strftime("%H:%M — %d %b"),
                "start_ts": now,
                "video":   display,
                "tag":     tag,
                "playlist": [os.path.basename(p) for p in existing],
                "mode":    "playlist" if len(existing) > 1 else "single",
                "reconnects": 0,
                "data_status": "sending",
                "healthy": True,
                "bg_video": bg_label,
                "elapsed": "00:00:00",
                "slug": self.slug,
            }

        self._spawn_ffmpeg()
        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitor_thread.start()

        print(f"[Stream:{self.slug}] CANLI YAYIN BASLADI — {display} — {rtmp_url}")
        return True, f"Yayın başlatıldı: {display}"

    def stop(self):
        with self.lock:
            self.stop_requested = True
            self.last_input_arg = None
            self.last_rtmp_url  = None

        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()

        self.process = None
        with self.lock:
            self.status = self._empty_status()
        print(f"[Stream:{self.slug}] YAYIN DURDURULDU")
        return True, "Yayın durduruldu."

    def get_status(self):
        with self.lock:
            alive = self.process and self.process.poll() is None
            if not self.status.get("reconnecting"):
                self.status["active"] = alive
            if not alive and not self.status.get("reconnecting"):
                self.status["healthy"] = False
            # Elapsed
            if alive and self.status.get("start_ts"):
                e = int(time.time() - self.status["start_ts"])
                self.status["elapsed"] = f"{e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d}"
            else:
                self.status["elapsed"] = "00:00:00"
            return dict(self.status)


# ── Session factory ────────────────────────────────────────────────────────────
def _get_session(slug: str) -> StreamSession:
    with _sessions_lock:
        if slug not in _sessions:
            _sessions[slug] = StreamSession(slug)
        return _sessions[slug]


# ── Public API ─────────────────────────────────────────────────────────────────
def start_stream(stream_key: str, video_path: str, loop: bool = True, channel_slug: str = "default"):
    return start_stream_playlist(stream_key, [video_path], tag="single",
                                 shuffle=False, channel_slug=channel_slug)


def start_stream_playlist(stream_key: str, video_paths: list,
                          tag: str = "", shuffle: bool = False,
                          bg_video_url: str = "", channel_slug: str = "default"):
    sess = _get_session(channel_slug)
    return sess.start(stream_key, video_paths, tag=tag, shuffle=shuffle, bg_video_url=bg_video_url)


def stop_stream(channel_slug: str = "default"):
    with _sessions_lock:
        if channel_slug not in _sessions:
            return False, "Bu kanal için aktif yayın yok."
    sess = _get_session(channel_slug)
    return sess.stop()


def get_status(channel_slug: str = None):
    """
    channel_slug verilirse o kanalın statusunu döner.
    None verilirse tüm aktif oturumların listesini döner.
    """
    if channel_slug:
        return _get_session(channel_slug).get_status()
    # Tüm aktif oturumlar — lock içinde session referanslarını kopyala
    with _sessions_lock:
        sessions_snapshot = list(_sessions.values())
    return [s.get_status() for s in sessions_snapshot]


def get_all_statuses() -> list:
    """Tüm kanalların stream durumunu döner."""
    with _sessions_lock:
        sessions_snapshot = list(_sessions.values())
    return [s.get_status() for s in sessions_snapshot]


def is_ffmpeg_installed() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def download_bg_video(url: str, dest: str = None) -> tuple:
    """URL'den arka plan videosunu indirir."""
    if dest is None:
        dest = BG_VIDEO_PATH
    try:
        if not url.startswith(('http://', 'https://')):
            return False, "Geçersiz URL"
        if os.path.exists(dest):
            os.remove(dest)

        if 'youtube.com' in url or 'youtu.be' in url:
            ytdlp_bin = "/usr/local/bin/yt-dlp"
            if not os.path.exists(ytdlp_bin):
                ytdlp_bin = "yt-dlp"
            result = subprocess.run(
                [ytdlp_bin, "--extractor-args", "youtube:player_client=android,web",
                 "-f", "bestvideo[height<=720][ext=mp4]/best[ext=mp4]/best",
                 "--no-playlist", "-o", dest, url],
                capture_output=True, timeout=300
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")[-300:]
                return False, f"YouTube indirilemedi: {err[-150:]}"
        else:
            result = subprocess.run(
                ["curl", "-L", "-s", "-o", dest,
                 "--user-agent", "Mozilla/5.0",
                 "--max-time", "120", url],
                capture_output=True, timeout=150
            )
            if result.returncode != 0:
                return False, f"İndirme hatası"

        if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
            return False, "İndirilen dosya geçersiz"
        return True, dest
    except subprocess.TimeoutExpired:
        return False, "İndirme zaman aşımına uğradı"
    except Exception as e:
        return False, str(e)
