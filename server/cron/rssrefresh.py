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


def should_refresh(feed_file: FeedFile, refresh_min_age: int = 24) -> bool:
    """
    Check if the file should be refreshed based on its age.
    
    Args:
        feed_file: FeedFile instance to check
        refresh_min_age: Minimum age in hours before refresh is needed
        
    Returns:
        True if file should be refreshed, False otherwise
    """
    age_hours = feed_file.get_file_age()
    
    if age_hours == float('inf'):
        LOGGER.info(f"📁 (Refresh needed) Feed File doesn't exist: {feed_file}")
        return True
    
    if age_hours > refresh_min_age:
        LOGGER.info(f"⏰ (Refresh needed) Feed file is {age_hours:.1f} hours old (>{refresh_min_age}h): {feed_file}")
        return True
    
    LOGGER.info(f"✅ (Refresh not needed) Feed file is {age_hours:.1f} hours old (≤{refresh_min_age}h): {feed_file}")
    return False


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


def parse_cron_schedule(schedule: str) -> tuple[int, int, int, int, int]:
    """
    Parse a cron schedule string.
    
    Args:
        schedule: Cron string "minute hour day month weekday" (e.g., "30 * * * *")
        
    Returns:
        Tuple of (minute, hour, day, month, weekday)
    """
    parts = schedule.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid schedule format: {schedule}. Expected 'minute hour day month weekday'")
    
    # Weekday mapping (Sunday=0, Monday=1, ..., Saturday=6)
    weekday_map = {
        'SUN': 0, 'SUNDAY': 0,
        'MON': 1, 'MONDAY': 1,
        'TUE': 2, 'TUESDAY': 2,
        'WED': 3, 'WEDNESDAY': 3,
        'THU': 4, 'THURSDAY': 4,
        'FRI': 5, 'FRIDAY': 5,
        'SAT': 6, 'SATURDAY': 6
    }
    
    minute = int(parts[0]) if parts[0] != '*' else None
    hour = int(parts[1]) if parts[1] != '*' else None
    day = int(parts[2]) if parts[2] != '*' else None
    month = int(parts[3]) if parts[3] != '*' else None
    
    # Parse weekday (supports numbers and strings)
    if parts[4] == '*':
        weekday = None
    elif parts[4].upper() in weekday_map:
        weekday = weekday_map[parts[4].upper()]
    else:
        weekday = int(parts[4])
    
    return minute, hour, day, month, weekday


def get_next_run_time(schedule: str) -> datetime:
    """
    Calculate the next run time based on cron schedule.
    
    Args:
        schedule: Cron string "minute hour day month weekday"
        
    Returns:
        Next datetime when the job should run
    """
    minute, hour, day, month, weekday = parse_cron_schedule(schedule)
    now = datetime.now()
    
    # Start with current time
    next_run = now.replace(second=0, microsecond=0)
    
    # Handle minute
    if minute is not None:
        if next_run.minute >= minute:
            # Minute has passed this hour, move to next hour
            next_run = next_run.replace(minute=minute) + timedelta(hours=1)
        else:
            # Minute hasn't passed yet this hour
            next_run = next_run.replace(minute=minute)
    else:
        # Every minute - run immediately
        return now
    
    # Handle hour
    if hour is not None:
        if next_run.hour >= hour:
            # Hour has passed today, move to next day
            next_run = next_run.replace(hour=hour) + timedelta(days=1)
        else:
            # Hour hasn't passed yet today
            next_run = next_run.replace(hour=hour)
    
    # Handle day
    if day is not None:
        if next_run.day >= day:
            # Day has passed this month, move to next month
            next_run = next_run.replace(day=day) + timedelta(days=30)
        else:
            # Day hasn't passed yet this month
            next_run = next_run.replace(day=day)
    
    # Handle month
    if month is not None:
        if next_run.month >= month:
            # Month has passed this year, move to next year
            next_run = next_run.replace(month=month) + timedelta(days=365)
        else:
            # Month hasn't passed yet this year
            next_run = next_run.replace(month=month)
    
    # Handle weekday (0=Sunday, 6=Saturday)
    if weekday is not None:
        # Calculate days until next occurrence of the weekday
        # datetime.weekday() returns 0=Monday, 6=Sunday, but cron uses 0=Sunday, 6=Saturday
        current_weekday = (next_run.weekday() + 1) % 7  # Convert to cron format (0=Sunday)
        days_until_weekday = (weekday - current_weekday) % 7
        if days_until_weekday == 0 and next_run.hour == hour and next_run.minute == minute:
            # We're already at the right time on the right day
            pass
        else:
            # Move to the next occurrence of the weekday
            next_run = next_run + timedelta(days=days_until_weekday)
    
    return next_run


async def rss_refresh_cron():
    """
    Background cron job that runs RSS refresh based on cron-like schedule.
    Gets configuration from settings file.
    """
    # Get configuration from settings
    feed_file = FeedFile(SETTINGS.get('feed', 'file'))
    schedule = SETTINGS.get('cron', 'refresh_schedule') or f"{random.randint(0, 59)} {random.randint(0, 23)} * * *"  # Default: every day at random minute/hour
    refresh_min_age = SETTINGS.get('cron', 'refresh_min_age') or 24  # Default: 24 hours

    LOGGER.info(f"🚀 RSS Refresh Cron Job started (schedule: {schedule})")
    LOGGER.info(f"📁 Feed file: {feed_file}")
    LOGGER.info(f"⏰ Max age: {refresh_min_age} hours")
    
    while True:
        try:
            # Calculate next run time
            next_run = get_next_run_time(schedule)
            now = datetime.now()
            
            # Calculate seconds until next run
            seconds_until_next = (next_run - now).total_seconds()
            
            if seconds_until_next > 0:
                LOGGER.info(f"⏰ Next RSS refresh check in {seconds_until_next // 60:.0f} minutes at {next_run.strftime('%Y-%m-%d %H:%M')}")
                await asyncio.sleep(seconds_until_next)
            
            # Check if refresh is needed
            if should_refresh(feed_file, refresh_min_age):
                await refresh_rss()
            else:
                LOGGER.info("😴 No RSS refresh needed")
                
        except Exception as e:
            LOGGER.error(f"❌ RSS refresh cron job error: {e}", exc_info=True)
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RSS Refresh Cron Job")
    p.add_argument("--feed-file", default=SETTINGS.get('feed', 'file'), help="Path to the feed file to refresh")
    p.add_argument("--min-age-hours", type=int, default=SETTINGS.get('cron', 'refresh_min_age'), help="Minimum age in hours before refresh is needed")
    p.add_argument("--schedule", default=SETTINGS.get('cron', 'refresh_schedule'), help="Cron schedule: minute hour day month weekday (e.g., '30 * * * *', '0 0 * * FRI')")
    p.add_argument("--daemon", action="store_true", help="Run as a daemon (continuous background process)")
    p.add_argument("--force", action="store_true", help="Force refresh regardless of file age")
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
    LOGGER.info(f"⏰ Min age: {args.min_age_hours or 0} hours")
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
