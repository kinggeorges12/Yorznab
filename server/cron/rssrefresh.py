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

from typing import Optional
from croniter import croniter
import argparse
import asyncio
import os
import random
import sys
import time
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


def get_next_run_time(schedule: str, base_time: Optional[datetime] = None) -> datetime:
    """
    Calculate the next run time based on cron schedule.
    
    Args:
        schedule: Cron string "minute hour day month weekday"
                 (e.g., "30 * * * *" or "*/15 * * * *" or "0 9-17 * * 1-5")
        base_time: Optional base time to calculate from. Defaults to now.
        
    Returns:
        Next datetime when the job should run
        
    Raises:
        ValueError: If the cron schedule is invalid
    """
    if base_time is None:
        base_time = datetime.now()
    
    # Validate and create cron iterator
    if not croniter.is_valid(schedule):
        raise ValueError(f"Invalid cron schedule: {schedule}")
    
    # Get the next run time
    cron = croniter(schedule, base_time)
    next_run = cron.get_next(datetime)
    
    return next_run

async def rss_refresh_cron():
    """
    Background cron job that runs RSS refresh based on cron-like schedule.
    Gets configuration from settings file.
    """
    # Get configuration from settings
    feed_file = FeedFile(SETTINGS.get('feed', 'file'))
    schedule = SETTINGS.get('cron', 'refresh_schedule') or f"{random.randint(0, 59)} {random.randint(0, 23)} * * *"  # Default: every day at random minute/hour

    LOGGER.info(f"🚀 RSS Refresh Cron Job started (schedule: {schedule})")
    LOGGER.info(f"📁 Feed file: {feed_file}")
    
    while True:
        try:
            # Calculate next run time
            now = datetime.now()
            next_run = get_next_run_time(schedule, now)
            
            # Calculate seconds until next run
            seconds_until_next = (next_run - now).total_seconds()
            
            if seconds_until_next > 0:
                LOGGER.info(f"⏰ Next RSS refresh check in {seconds_until_next // 60:.0f} minutes at {next_run.strftime('%Y-%m-%d %H:%M')}")
                await asyncio.sleep(seconds_until_next)
            
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
