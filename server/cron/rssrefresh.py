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
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add the parent directory to the path so we can import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.customlogger import CustomLogger
from utils.settings import AppSettings
import asyncio

# Global logger instance
logger = CustomLogger()

# Load settings from config file
SETTINGS = AppSettings('app.yaml')

def get_file_age_hours(file_path: str) -> float:
    """
    Get the age of a file in hours.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        Age in hours, or float('inf') if file doesn't exist
    """
    if not os.path.exists(file_path):
        return float('inf')
    
    file_mtime = os.path.getmtime(file_path)
    current_time = time.time()
    age_seconds = current_time - file_mtime
    age_hours = age_seconds / 3600
    
    return age_hours


def should_refresh(file_path: str, min_age_hours: int = 24) -> bool:
    """
    Check if the file should be refreshed based on its age.
    
    Args:
        file_path: Path to the file to check
        min_age_hours: Minimum age in hours before refresh is needed
        
    Returns:
        True if file should be refreshed, False otherwise
    """
    age_hours = get_file_age_hours(file_path)
    
    if age_hours == float('inf'):
        logger.info(f"📁 File {file_path} doesn't exist - refresh needed")
        return True
    
    if age_hours > min_age_hours:
        logger.info(f"⏰ File {file_path} is {age_hours:.1f} hours old (>{min_age_hours}h) - refresh needed")
        return True
    
    logger.info(f"✅ File {file_path} is {age_hours:.1f} hours old (≤{min_age_hours}h) - no refresh needed")
    return False


async def refresh_rss() -> bool:
    """
    Refresh the RSS feed by calling the webhook run_requests function.
    
    Returns:
        True if refresh was successful, False otherwise
    """
    try:
        logger.info(f"🔄 Starting RSS refresh via webhook run_requests")
        
        # Import the webhook module and call run_requests
        from routers import webhook
        
        # Call run_requests with no parameters to process both Movies and TV
        result = await webhook.run_requests()
        
        if result == 0:
            logger.info(f"✅ RSS refresh completed successfully")
            return True
        else:
            logger.error(f"❌ RSS refresh failed with exit code {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ RSS refresh failed with exception: {e}", exc_info=True)
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
    feed_file = SETTINGS.get('feed', 'file')
    schedule = SETTINGS.get('rss', 'refresh_schedule')
    min_age_hours = SETTINGS.get('rss', 'refresh_max_age')

    logger.info(f"🚀 RSS refresh cron job started (schedule: {schedule})")
    logger.info(f"📁 Feed file: {feed_file}")
    logger.info(f"⏰ Max age: {min_age_hours} hours")
    
    while True:
        try:
            # Calculate next run time
            next_run = get_next_run_time(schedule)
            now = datetime.now()
            
            # Calculate seconds until next run
            seconds_until_next = (next_run - now).total_seconds()
            
            if seconds_until_next > 0:
                logger.info(f"⏰ Next RSS refresh check in {seconds_until_next // 60:.0f} minutes at {next_run.strftime('%Y-%m-%d %H:%M')}")
                await asyncio.sleep(seconds_until_next)
            
            # Check if refresh is needed
            if should_refresh(feed_file, min_age_hours):
                await refresh_rss()
            else:
                logger.info("😴 No RSS refresh needed")
                
        except Exception as e:
            logger.error(f"❌ RSS refresh cron job error: {e}", exc_info=True)
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RSS Refresh Cron Job")
    p.add_argument("--feed-file", default=SETTINGS.get('feed', 'file'), help="Path to the feed file to refresh")
    p.add_argument("--min-age-hours", type=int, default=SETTINGS.get('rss', 'refresh_max_age'), help="Minimum age in hours before refresh is needed")
    p.add_argument("--force", action="store_true", help="Force refresh regardless of file age")
    p.add_argument("--schedule", default=SETTINGS.get('rss', 'refresh_schedule'), help="Cron schedule: minute hour day month weekday (e.g., '30 * * * *', '0 0 * * FRI')")
    p.add_argument("--daemon", action="store_true", help="Run as a daemon (continuous background process)")
    return p.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Main function for the cron job."""
    args = parse_args(argv)
    
    # Convert relative paths to absolute paths
    feed_file = os.path.abspath(args.feed_file)
    
    logger.info(f"🚀 RSS Refresh Cron Job started")
    logger.info(f"📁 Feed file: {feed_file}")
    logger.info(f"⏰ Max age: {args.min_age_hours} hours")
    logger.info(f"🕐 Schedule: {args.schedule}")
    
    # Run once on start
    success = await refresh_rss()
    if success:
        logger.info("🎉 RSS refresh cron job completed successfully")
        return 0
    else:
        logger.error("💥 RSS refresh cron job failed")
        return 1
    
    if args.daemon:
        # Run as a daemon (continuous background process)
        logger.info("🔄 Running as daemon...")
        try:
            await rss_refresh_cron()
        except KeyboardInterrupt:
            logger.info("🛑 Daemon stopped by user")
            return 0

def main_cron(argv: list[str] | None = None) -> int:
    """Synchronous wrapper for cron compatibility."""
    return asyncio.run(main(argv))


if __name__ == "__main__":
    exit_code = main_cron()
    sys.exit(exit_code)
