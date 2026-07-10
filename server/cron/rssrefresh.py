#!/usr/bin/env python3
"""
RSS Refresh Cron Job

Automatically refreshes the torrent.json file if it hasn't been changed in the past 24 hours.
Can be used as a standalone cron job or integrated with FastAPI.

Usage:
    python cron/rssrefresh.py

Cron job example (runs at minute 30 every hour):
    30 * * * * /usr/bin/python3 /path/to/cron/rssrefresh.py
"""

import os
from typing import Optional
from threading import Lock
from zoneinfo import ZoneInfo
from croniter import croniter
import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the parent directory to the path so we can import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

# First time message
from server.utils.keystore import KeyStore
HELLO_WORLD = 'This is your first run! Welcome to Yorznab 🤗' if not KeyStore.exists() else None

from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings
from server.utils.feedconfig import FeedConfig
import asyncio

# Global logger instance
LOGGER:CustomLogger = CustomLogger(name="cron", enable_log=True)

# Load settings from config file
SETTINGS:AppSettings = AppSettings(filename='yorznab.yaml')

# Load settings from config file
FEED:AppSettings = AppSettings(filename='feed.yaml')

# Load default args
FEED_CONFIGS:list[FeedConfig] = []
REFRESH_SCHEDULE:str = SETTINGS.get('cron', 'refresh_schedule') or f"{random.randint(0, 59)} {random.randint(0, 23)} * * *"
DOWNLOAD:bool = os.environ.get('DOWNLOAD','false').lower() not in ['false', 'no'] and bool(os.environ.get('DOWNLOAD'))
NEXT_RUN:Optional[datetime] = None

# Get timezone from Docker environment variable, fallback to UTC
TIMEZONE_STR:str = os.environ.get('TZ', 'UTC')
TIMEZONE:ZoneInfo = ZoneInfo(TIMEZONE_STR)

class CronRunner:

    """
    Class to manage the RSS refresh cron job.
    """
    _instance = None
    _lock = Lock()
    _initialized = False
    _status:str = "Initializing"
    _timezone_str:str = TIMEZONE_STR
    _timezone:ZoneInfo = ZoneInfo(_timezone_str)

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        global FEED_CONFIGS, REFRESH_SCHEDULE, DOWNLOAD, NEXT_RUN, TIMEZONE_STR
        if not self.__class__._initialized:
            self._feed_configs:list[FeedConfig] = FEED_CONFIGS
            self.refresh_schedule:str = REFRESH_SCHEDULE
            self.download:bool = DOWNLOAD
            self._next_run:Optional[datetime] = NEXT_RUN
            self.__class__._status = "Started"
            self.__class__._initialized = True

    @classmethod
    def status(cls) -> str:
        """Get the current status."""
        return cls._status

    @property
    def next_run(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        return self._next_run

    @property
    def feed_configs(self) -> list[FeedConfig]:
        """Get the list of feed configurations."""
        return self._feed_configs

    async def refresh_rss(self, feed_configs: list[FeedConfig] | None = None) -> bool:
        """
        Refresh the RSS feed by calling the webhook run_requests function.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        global FEED_CONFIGS, REFRESH_SCHEDULE, DOWNLOAD
        with self.__class__._lock: self.__class__._status = "Running"
        try:
            # Import the webhook module and call run_requests
            from routers import webhook
            
            # Call run_requests with no server_type to process both Movies and TV
            run_configs = feed_configs or FEED_CONFIGS
            LOGGER.info(f"🔄 Starting RSS refresh: {', '.join([rc.config_name for rc in run_configs])}")
            
            result = await webhook.run_requests(feed_configs=run_configs)
            
            if result == 0:
                LOGGER.info(f"✅ RSS refresh completed successfully")
                return True
            else:
                LOGGER.error(f"❌ RSS refresh failed with exit code {result}")
                
        except Exception as e:
            LOGGER.error(f"❌ RSS refresh failed with exception: {e}", exc_info=True)

        with self.__class__._lock: self.__class__._status = "Failure"
        return False

    @classmethod
    def get_now(cls) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(cls._timezone)


    def get_next_run_time(self, schedule: Optional[str] = None, base_time: Optional[datetime] = None) -> datetime:
        """
        Calculate the next run time based on cron schedule.
        
        Args:
            schedule: Cron string "minute hour day month weekday"
                    (e.g., "30 * * * *" or "*/15 * * * *" or "0 9-17 * * 1-5")
            base_time: Optional base time to calculate from. Defaults to now.
            
        Returns:
            Next datetime when the job should run (timezone-aware)
            
        Raises:
            ValueError: If the cron schedule is invalid
        """
        global TIMEZONE
        
        if base_time is None:
            base_time = self.__class__.get_now().replace(tzinfo=self.__class__._timezone)
        
        # Validate and create cron iterator
        if not croniter.is_valid(schedule):
            raise ValueError(f"Invalid cron schedule: {schedule}")
        
        # Get the next run time
        cron = croniter(schedule, start_time=base_time, expand_from_start_time=True)
        next_run = cron.get_next(datetime)
        
        # Ensure the result is timezone-aware
        if next_run.tzinfo is None or next_run.tzinfo.utcoffset(next_run) is None:
            next_run = next_run.replace(tzinfo=self.__class__._timezone)
        
        return next_run


    async def rss_refresh_cron(self):
        """
        Background cron job that runs RSS refresh based on cron-like schedule.
        Gets configuration from settings file.
        """

        # Default: every day at random minute/hour
        schedule = self.refresh_schedule

        LOGGER.info(f"🚀 RSS Refresh Cron Job started (schedule: {schedule})")
        LOGGER.info(f"🌎 Timezone: {self.__class__._timezone_str}")
        
        while True:
            try:
                LOGGER.info(f"📁 Feed file(s): {', '.join(str(f.file) for f in self.feed_configs)}")
                need_refresh = []
                max_file_age = 0
                for feed_config in self.feed_configs:
                    # Check file age in case the cron shut down since last run
                    feed_file_age = feed_config.file_age
                    max_file_age = feed_file_age if feed_file_age > max_file_age else max_file_age
                    
                    # If file doesn't exist, run immediately
                    if feed_file_age == float('inf'):
                        LOGGER.warning("⚠️ Feed file doesn't exist - running immediate refresh")
                        need_refresh.append(feed_config)
                if need_refresh:
                    await self.refresh_rss(feed_configs=need_refresh)
                    # Recheck oldest feed file and continue
                    continue
                
                # Calculate the file's modification time from its age
                now = self.__class__.get_now()
                file_mtime = now - timedelta(seconds=max_file_age)

                # Calculate next run time based on when the file was last modified
                next_run = self.get_next_run_time(schedule, file_mtime)
                
                # Calculate seconds until next run from current time
                seconds_until_next = (next_run - now).total_seconds()

                # Save next run for front-end
                self._next_run = next_run
                
                if seconds_until_next > 0:
                    log_time = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
                    LOGGER.info(f"⏰ Next RSS refresh in {seconds_until_next // 60:.0f} minutes at {log_time}")
                    with self.__class__._lock: self.__class__._status =  "Sleeping"
                    await asyncio.sleep(seconds_until_next)
                else:
                    LOGGER.warning("🔔 Missed an RSS refresh on the schedule - running immediate refresh")

                # Wait for refresh to finish before starting cron timer again
                await self.refresh_rss()
                    
            except Exception as e:
                LOGGER.error(f"❌ RSS refresh cron job error: {e}", exc_info=True)
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RSS Refresh Cron Job")
    p.add_argument("--feeds", type=str, default=None, help="Comma-separated list of configuration file(s) for filtering and serving torrent feeds (default=config/feed.yaml).")
    p.add_argument("--schedule", default=None, help="Cron schedule: minute hour day month weekday (e.g., '30 * * * *', '0 0 * * FRI')")
    p.add_argument("--daemon", action="store_true", help="Run as a daemon (continuous background process)")
    p.add_argument("--force", action="store_true", help="Force refresh now")
    return p.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Main function for the cron job."""
    global FEED_CONFIGS, REFRESH_SCHEDULE, DOWNLOAD, NEXT_RUN
    args = parse_args(argv)

    # Get feed file from config
    feed_missing = []
    feeds = args.feeds or os.environ.get('FEEDS') or ""
    for feed_config_path in feeds.split(','):
        feed_config = FeedConfig(feed_config_path.strip())
        if not feed_config.path.exists():
            feed_missing.append(feed_config)
        FEED_CONFIGS.append(feed_config)

    # Set defaults from args
    FEED_CONFIGS = FEED_CONFIGS or [FeedConfig()]  # Default to feed.yaml if none specified
    REFRESH_SCHEDULE = args.schedule or REFRESH_SCHEDULE
    NEXT_RUN = CronRunner.get_now()  # Current time for first run

    # Determine whether we need to refresh the feed
    force_msg = HELLO_WORLD
    force_msg = 'Command line argument "--force"' if not force_msg and args.force else force_msg
    force_msg = f"RSS Feed(s) missing: {', '.join(str(f.path) for f in feed_missing)}" if not force_msg and feed_missing else force_msg
    
    LOGGER.info(f"🚀 RSS Refresh Cron initializing")
    if (FEED_CONFIGS):
        LOGGER.info(f"🔎 Feed config(s): {', '.join(str(f.config_path) for f in FEED_CONFIGS)}")
    LOGGER.info(f"⚡ Run now: {force_msg or 'Nope'}")
    if (DOWNLOAD):
        LOGGER.info(f"📥 Download top result: {DOWNLOAD}")
    LOGGER.info(f"🕐 Schedule: {REFRESH_SCHEDULE}")
    LOGGER.info(f"🌎 Timezone: {TIMEZONE_STR}")
    
    # Initialize the cron runner
    cron_runner = CronRunner()

    # Force refresh on first run
    if args.force or HELLO_WORLD:
        success = await cron_runner.refresh_rss()
    elif feed_missing:
        success = await cron_runner.refresh_rss(feed_missing)

    if args.daemon:
        # Run as a daemon (continuous background process)
        LOGGER.info("🔄 Running as daemon...")
        try:
            await cron_runner.rss_refresh_cron()
        except KeyboardInterrupt:
            LOGGER.info("🛑 Daemon stopped by user")
            return 0
    else:
        if success:
            LOGGER.info("🎉 RSS refresh completed successfully")
            return 0
        else:
            LOGGER.error("💥 RSS refresh failed")
            return 1

def main_cron(argv: list[str] | None = None) -> int:
    """Synchronous wrapper for cron compatibility."""
    return asyncio.run(main(argv))


if __name__ == "__main__":
    exit_code = main_cron()
    sys.exit(exit_code)
