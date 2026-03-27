# Zamanlayıcı Modülü — APScheduler + Georgia/Eastern Time
import uuid
import json
import os
import threading
import atexit
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

EASTERN     = pytz.timezone('America/New_York')   # Georgia = Eastern Time
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCHED_FILE  = os.path.join(BASE_DIR, 'schedules.json')

_scheduler      = BackgroundScheduler(timezone=EASTERN)
_run_flow_fn    = None   # app.py'den enjekte edilir (circular import'tan kaçınmak için)
_enqueue_fn     = None   # app.py'den enjekte edilir — queue limit doğru çalışsın
_sched_lock     = threading.Lock()

# ── Disk I/O ──────────────────────────────────────────────────────────────────

def _atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def load_schedules():
    try:
        if os.path.exists(SCHED_FILE):
            with open(SCHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_schedules(schedules):
    with _sched_lock:
        _atomic_write(SCHED_FILE, schedules)

# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _all():
    return load_schedules()

def _find(sid):
    return next((s for s in _all() if s['id'] == sid), None)

def _next_run_str(sched):
    """APScheduler'dan bir sonraki çalışma zamanını Eastern olarak döner."""
    try:
        job = _scheduler.get_job(sched['id'])
        if job and job.next_run_time:
            return job.next_run_time.astimezone(EASTERN).strftime('%Y-%m-%d %I:%M %p ET')
    except Exception:
        pass
    return '—'

# ── APScheduler Job Sync ──────────────────────────────────────────────────────

def _job_wrapper(schedule_id):
    """APScheduler bu fonksiyonu tetikler."""
    schedules = _all()
    sched = next((s for s in schedules if s['id'] == schedule_id), None)
    if not sched or not sched.get('enabled'):
        return
    print(f"[Scheduler] Zamanlanmış görev çalıştırılıyor: {sched['name']}")
    sched['last_run'] = datetime.now(EASTERN).strftime('%Y-%m-%d %I:%M %p ET')
    sched['run_count'] = sched.get('run_count', 0) + 1
    save_schedules(schedules)
    if not _run_flow_fn:
        print(f"[Scheduler] HATA: run_flow_fn atanmamis, gorev atlandi: {sched['name']}")
        return
    try:
        args = (
            sched['genre'],
            sched.get('style', 'Cinematic'),
            sched.get('lyrics_enabled', True),
            True,
            sched.get('channel_slug') or None,
            int(sched.get('min_duration', 0)),
        )
        if _enqueue_fn:
            # Queue üzerinden çalıştır — MAX_CONCURRENT_JOBS limiti korunur
            _enqueue_fn(_run_flow_fn, *args)
        else:
            _run_flow_fn(*args)
    except Exception as e:
        print(f"[Scheduler] Görev hatası ({sched['name']}): {e}")

def _sync_job(sched):
    """Schedule'a ait APScheduler job'unu ekler / günceller / kaldırır."""
    sid = sched['id']
    try:
        _scheduler.remove_job(sid)
    except Exception:
        pass

    if not sched.get('enabled'):
        return

    trigger = CronTrigger(
        day_of_week=sched.get('days_of_week', '*'),
        hour=sched.get('time_hour', 12),
        minute=sched.get('time_minute', 0),
        timezone=EASTERN,
    )
    _scheduler.add_job(
        _job_wrapper,
        trigger,
        args=[sid],
        id=sid,
        name=sched.get('name', sid),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
    )

# ── Public API ────────────────────────────────────────────────────────────────

def init_scheduler(run_flow_fn, enqueue_fn=None):
    """app.py başlarken bir kez çağrılır."""
    global _run_flow_fn, _enqueue_fn
    _run_flow_fn = run_flow_fn
    _enqueue_fn  = enqueue_fn

    if not _scheduler.running:
        _scheduler.start()
        atexit.register(lambda: _scheduler.shutdown(wait=False))

    for sched in _all():
        if sched.get('enabled'):
            try:
                _sync_job(sched)
            except Exception as e:
                print(f"[Scheduler] Job restore hatası ({sched['id']}): {e}")

    print(f"[Scheduler] {len([s for s in _all() if s.get('enabled')])} aktif zamanlama yüklendi.")


def list_schedules():
    schedules = _all()
    for s in schedules:
        s['next_run'] = _next_run_str(s)
    return schedules


def get_schedule(sid):
    s = _find(sid)
    if s:
        s['next_run'] = _next_run_str(s)
    return s


def add_schedule(data):
    schedules = _all()
    sched = {
        'id':            str(uuid.uuid4()),
        'name':          data.get('name', 'New Schedule').strip(),
        'genre':         data.get('genre', 'Lofi Chill').strip(),
        'style':         data.get('style', 'Cinematic'),
        'lyrics_enabled':bool(data.get('lyrics_enabled', True)),
        'days_of_week':  data.get('days_of_week', '*'),   # "*" = her gün
        'time_hour':     int(data.get('time_hour', 12)),
        'time_minute':   int(data.get('time_minute', 0)),
        'enabled':       bool(data.get('enabled', True)),
        'channel_slug':  data.get('channel_slug', '') or '',
        'min_duration':  int(data.get('min_duration', 0)),
        'created_at':    datetime.now(EASTERN).strftime('%Y-%m-%d %I:%M %p ET'),
        'last_run':      None,
        'run_count':     0,
    }
    schedules.append(sched)
    save_schedules(schedules)
    _sync_job(sched)
    sched['next_run'] = _next_run_str(sched)
    return sched


def update_schedule(sid, data):
    schedules = _all()
    sched = next((s for s in schedules if s['id'] == sid), None)
    if not sched:
        return None
    fields = ['name', 'genre', 'style', 'lyrics_enabled', 'days_of_week',
              'time_hour', 'time_minute', 'enabled', 'channel_slug', 'min_duration']
    for k in fields:
        if k in data:
            val = data[k]
            if k in ('time_hour', 'time_minute'):
                val = int(val)
            elif k in ('lyrics_enabled', 'enabled'):
                val = bool(val)
            sched[k] = val
    save_schedules(schedules)
    _sync_job(sched)
    sched['next_run'] = _next_run_str(sched)
    return sched


def delete_schedule(sid):
    schedules = _all()
    new_list = [s for s in schedules if s['id'] != sid]
    if len(new_list) == len(schedules):
        return False
    save_schedules(new_list)
    try:
        _scheduler.remove_job(sid)
    except Exception:
        pass
    return True


def toggle_schedule(sid, enabled):
    return update_schedule(sid, {'enabled': enabled})


def run_now(sid):
    """Anında bir kez çalıştır (test amaçlı) — queue üzerinden, limit korunur."""
    sched = _find(sid)
    if not sched:
        return False
    # _job_wrapper'ı enqueue üzerinden çalıştır (MAX_CONCURRENT_JOBS korunsun)
    import threading
    t = threading.Thread(target=_job_wrapper, args=[sid], daemon=True)
    t.start()
    return True
