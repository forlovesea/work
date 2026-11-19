from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

SEOUL = ZoneInfo("Asia/Seoul")


def triggers(config):
    config.validate()
    for value in config.times:
        hour, minute = map(int, value.split(":"))
        yield CronTrigger(hour=hour, minute=minute, day_of_week=",".join(map(str, config.weekdays)), timezone=SEOUL)


def missed_schedule(config, last_seen, now):
    if not config.schedule_enabled or not last_seen:
        return False
    then = datetime.fromisoformat(last_seen)
    return any(trigger.get_next_fire_time(None, then) <= now for trigger in triggers(config))


class ScheduleEngine:
    def __init__(self, dispatch, warning=None):
        self.dispatch = dispatch
        self.warning = warning or (lambda message: None)
        self.scheduler = BackgroundScheduler(timezone=SEOUL)
        self.scheduler.add_listener(self.on_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED)
        self.scheduler.start(paused=True)

    def on_event(self, event):
        message = "예약 실행 시각을 놓쳐 작업을 건너뛰었습니다." if event.code == EVENT_JOB_MISSED else "예약 실행 전달 중 오류가 발생했습니다."
        self.warning(message)

    def apply(self, config):
        self.scheduler.remove_all_jobs()
        if config.schedule_enabled:
            for i, trigger in enumerate(triggers(config)):
                self.scheduler.add_job(self.dispatch, trigger, id=str(i), coalesce=True,
                                       max_instances=1, misfire_grace_time=60)
            self.scheduler.resume()
        else:
            self.scheduler.pause()

    def next_runs(self):
        return [job.next_run_time.astimezone(SEOUL).strftime("%Y-%m-%d %H:%M") for job in self.scheduler.get_jobs() if job.next_run_time]

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
