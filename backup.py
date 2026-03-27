"""
Otomatik Backup Modülü
- Eski videoları /root/Yt/archive/ klasörüne taşır
- Disk dolduğunda en eski dosyaları siler
- Günlük temizlik çalışır
"""
import os
import shutil
import time
import json
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR  = os.path.join(BASE_DIR, 'outputs')
ARCHIVE_DIR = os.path.join(BASE_DIR, 'archive')
LOG_FILE    = os.path.join(BASE_DIR, 'backup.log')

# Ayarlar
KEEP_VIDEOS_DAYS   = 30    # MP4 dosyaları kaç gün tutulsun
KEEP_IMAGES_DAYS   = 60    # JPG dosyaları kaç gün tutulsun
KEEP_MUSIC_DAYS    = 30    # MP3 dosyaları kaç gün tutulsun
DISK_WARN_PCT      = 85    # Disk doluluk uyarı eşiği (%)
DISK_CLEAN_PCT     = 90    # Bu eşiği geçince otomatik sil


def _log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def get_disk_usage():
    """Disk doluluk yüzdesini döner."""
    try:
        stat = shutil.disk_usage(BASE_DIR)
        return round(stat.used / stat.total * 100, 1), stat.free
    except Exception:
        return 0.0, 0


def archive_old_files(dry_run=False):
    """KEEP_*_DAYS'den eski dosyaları archive/ klasörüne taşır."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    now = time.time()
    moved = []

    ext_age = {
        '.mp4':  KEEP_VIDEOS_DAYS * 86400,
        '.mp3':  KEEP_MUSIC_DAYS  * 86400,
        '.jpg':  KEEP_IMAGES_DAYS * 86400,
        '.jpeg': KEEP_IMAGES_DAYS * 86400,
    }

    for fname in os.listdir(VIDEOS_DIR):
        fpath = os.path.join(VIDEOS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext  = os.path.splitext(fname)[1].lower()
        age  = ext_age.get(ext)
        if not age:
            continue
        file_age = now - os.path.getmtime(fpath)
        if file_age > age:
            dest = os.path.join(ARCHIVE_DIR, fname)
            if not dry_run:
                shutil.move(fpath, dest)
            moved.append(fname)
            _log(f"Arşivlendi: {fname} (yaş: {int(file_age/86400)} gün)")

    return moved


def cleanup_by_disk(target_pct=80):
    """Disk doluluk %DISK_CLEAN_PCT'yi aşınca en eski dosyaları siler."""
    pct, _ = get_disk_usage()
    if pct < DISK_CLEAN_PCT:
        return []

    _log(f"Disk doluluk {pct}% — temizlik başlıyor (hedef: {target_pct}%)")
    deleted = []

    # Önce archive'den, sonra outputs'tan sil (en eskisi önce)
    for folder in [ARCHIVE_DIR, VIDEOS_DIR]:
        if not os.path.exists(folder):
            continue
        files = sorted(
            [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))],
            key=os.path.getmtime
        )
        for fpath in files:
            pct, _ = get_disk_usage()
            if pct < target_pct:
                break
            os.remove(fpath)
            deleted.append(os.path.basename(fpath))
            _log(f"Silindi (disk temizlik): {os.path.basename(fpath)}")

    return deleted


def get_backup_stats():
    """Backup durum özeti döner."""
    pct, free_bytes = get_disk_usage()
    free_gb = round(free_bytes / (1024**3), 1)

    outputs_size = sum(
        os.path.getsize(os.path.join(VIDEOS_DIR, f))
        for f in os.listdir(VIDEOS_DIR)
        if os.path.isfile(os.path.join(VIDEOS_DIR, f))
    ) if os.path.exists(VIDEOS_DIR) else 0

    archive_size = sum(
        os.path.getsize(os.path.join(ARCHIVE_DIR, f))
        for f in os.listdir(ARCHIVE_DIR)
        if os.path.isfile(os.path.join(ARCHIVE_DIR, f))
    ) if os.path.exists(ARCHIVE_DIR) else 0

    archive_count = len(os.listdir(ARCHIVE_DIR)) if os.path.exists(ARCHIVE_DIR) else 0

    return {
        "disk_pct":      pct,
        "disk_free_gb":  free_gb,
        "disk_warn":     pct >= DISK_WARN_PCT,
        "outputs_mb":    round(outputs_size / (1024**2), 1),
        "archive_mb":    round(archive_size  / (1024**2), 1),
        "archive_count": archive_count,
    }


def run_daily_backup():
    """Scheduler tarafından günlük çağrılır."""
    _log("Günlük backup başladı")
    moved   = archive_old_files()
    deleted = cleanup_by_disk()
    stats   = get_backup_stats()
    _log(f"Backup tamamlandı — arşivlendi: {len(moved)}, silindi: {len(deleted)}, disk: {stats['disk_pct']}%")
    return {"moved": moved, "deleted": deleted, "stats": stats}
