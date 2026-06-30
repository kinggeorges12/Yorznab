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
from server.utils.feedfile import FeedFile
import asyncio

# Global logger instance
LOGGER = CustomLogger(name="cron", enable_log=True)

# Load settings from config file
SETTINGS = AppSettings(filename='yorznab.yaml')

# Get timezone from Docker environment variable, fallback to UTC
TIMEZONE_STR = os.environ.get('TZ', 'UTC')
TIMEZONE = ZoneInfo(TIMEZONE_STR)

async def refresh_rss() -> bool:
    """
    Refresh the RSS feed by calling the webhook run_requests function.
    
    Returns:
        True if refresh was successful, False otherwise
    """
    try:
        LOGGER.info(f"🔄 Starting RSS refresh via webhook run_requests")
        
        # Import the webhook module and call run_requests
        from routers import webhook
        
        # Call run_requests with no parameters to process both Movies and TV
        result = await webhook.run_requests()
        
        if result == 0:
            LOGGER.info(f"✅ RSS refresh completed successfully")
            return True
        else:
            LOGGER.error(f"❌ RSS refresh failed with exit code {result}")
            return False
            
    except Exception as e:
        LOGGER.error(f"❌ RSS refresh failed with exception: {e}", exc_info=True)
        return False


def get_now() -> datetime:
    """Get current time in the configured timezone."""
    return datetime.now(TIMEZONE)


def get_next_run_time(schedule: str, base_time: Optional[datetime] = None) -> datetime:
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
    if base_time is None:
        base_time = get_now()
    
    # Ensure base_time is timezone-aware
    if base_time.tzinfo is None or base_time.tzinfo.utcoffset(base_time) is None:
        base_time = base_time.replace(tzinfo=TIMEZONE)
    
    # Validate and create cron iterator
    if not croniter.is_valid(schedule):
        raise ValueError(f"Invalid cron schedule: {schedule}")
    
    # Get the next run time
    cron = croniter(schedule, base_time)
    next_run = cron.get_next(datetime)
    
    # Ensure the result is timezone-aware
    if next_run.tzinfo is None or next_run.tzinfo.utcoffset(next_run) is None:
        next_run = next_run.replace(tzinfo=TIMEZONE)
    
    return next_run


async def rss_refresh_cron():
    """
    Background cron job that runs RSS refresh based on cron-like schedule.
    Gets configuration from settings file.
    """
    # Get configuration from settings
    feed_file = FeedFile(SETTINGS.get('feed', 'file'))
    # Default: every day at random minute/hour
    schedule = SETTINGS.get('cron', 'refresh_schedule') or f"{random.randint(0, 59)} {random.randint(0, 23)} * * *"

    LOGGER.info(f"🚀 RSS Refresh Cron Job started (schedule: {schedule})")
    LOGGER.info(f"📁 Feed file: {feed_file}")
    LOGGER.info(f"🌎 Timezone: {TIMEZONE_STR}")
    
    while True:
        try:
            # Check file age in case the cron shut down since last run
            feed_file_age = feed_file.get_file_age()
            
            # If file doesn't exist, run immediately
            if feed_file_age == float('inf'):
                LOGGER.warning("⚠️ Feed file doesn't exist - running immediate refresh")
                await refresh_rss()
                continue

            # Calculate the file's modification time from its age
            now = get_now()
            file_mtime = now - timedelta(seconds=feed_file_age)
            
            # Ensure file_mtime is timezone-aware (assume UTC for file times)
            if file_mtime.tzinfo is None or file_mtime.tzinfo.utcoffset(file_mtime) is None:
                file_mtime = file_mtime.replace(tzinfo=ZoneInfo('UTC')).astimezone(TIMEZONE)
            
            # Calculate next run time based on when the file was last modified
            next_run = get_next_run_time(schedule, file_mtime)
            
            # Calculate seconds until next run from current time
            seconds_until_next = (next_run - now).total_seconds()
            
            if seconds_until_next > 0:
                log_time = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
                LOGGER.info(f"⏰ Next RSS refresh in {seconds_until_next // 60:.0f} minutes at {log_time}")
                await asyncio.sleep(seconds_until_next)
            else:
                LOGGER.warning("🔔 Missed an RSS refresh on the schedule - running immediate refresh")
            
            # Wait for refresh to finish before starting cron timer again
            await refresh_rss()
                
        except Exception as e:
            LOGGER.error(f"❌ RSS refresh cron job error: {e}", exc_info=True)
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RSS Refresh Cron Job")
    p.add_argument("--feed-file", default=SETTINGS.get('feed', 'file'), help="Path to the feed file to refresh")
    p.add_argument("--schedule", default=SETTINGS.get('cron', 'refresh_schedule'), help="Cron schedule: minute hour day month weekday (e.g., '30 * * * *', '0 0 * * FRI')")
    p.add_argument("--daemon", action="store_true", help="Run as a daemon (continuous background process)")
    p.add_argument("--force", action="store_true", help="Force refresh now")
    return p.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Main function for the cron job."""
    args = parse_args(argv)
    
    # Get feed file from config
    feed_file = FeedFile(args.feed_file or SETTINGS.get('feed', 'file'))

    # Determine whether we need to refresh the feed
    force_msg = HELLO_WORLD
    force_msg = 'Command line argument "--force"' if not force_msg and args.force else force_msg
    force_msg = 'RSS Feed missing' if not force_msg and not feed_file.exists() else force_msg
    
    LOGGER.info(f"🚀 RSS Refresh Cron initializing")
    LOGGER.info(f"⚡ Run now: {force_msg or 'Nope'}")
    LOGGER.info(f"📁 Feed file: {feed_file}")
    LOGGER.info(f"🕐 Schedule: {args.schedule}")
    LOGGER.info(f"🌎 Timezone: {TIMEZONE_STR}")
    
    # Force refresh on first run
    if force_msg:
        success = await refresh_rss()
    
    if args.daemon:
        # Run as a daemon (continuous background process)
        LOGGER.info("🔄 Running as daemon...")
        try:
            await rss_refresh_cron()
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
