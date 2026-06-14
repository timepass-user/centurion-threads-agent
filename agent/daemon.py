"""Local autonomous runner — cycles every 2 hours without GitHub Actions."""
from __future__ import annotations

import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .main import cycle
from .state import State
from .threads_client import ThreadsClient

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("centurion")


def run_daemon(state: State, tc: ThreadsClient) -> None:
    scheduler = BlockingScheduler()

    def job():
        logger.info("=== Centurion cycle starting ===")
        try:
            cycle(state, tc)
        except Exception as e:
            logger.error("Cycle failed: %s", e)

    # Run immediately on start, then every 2 hours
    job()
    scheduler.add_job(job, IntervalTrigger(hours=2), id="centurion_cycle")
    logger.info("Daemon running — cycle every 2h. Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon stopped.")
