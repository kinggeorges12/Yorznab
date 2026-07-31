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
import argparse
import asyncio
import sys

# First time message
from server.cron.CronRunner import CronRunner
from server.entities.YorznabClient import YorznabClient
from server.utils.keystore import KeyStore
HELLO_WORLD = 'This is your first run! Welcome to Yorznab 🤗' if not KeyStore.exists() else None

from server.utils.customlogger import CustomLogger
from server.utils.timeformatter import TimezoneAware
import asyncio

# Global logger instance
LOGGER = CustomLogger(name="rss")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RSS Refresh Cron Job")
    p.add_argument("--feeds", type=str, default=None, help="Comma-separated list of feed names in the config directory (by default, reads all yaml files in /app/config/feeds/*.yaml)")
    p.add_argument("--schedule", default=None, help="Cron schedule: minute hour day month weekday (e.g., '30 * * * *', '0 0 * * FRI')")
    p.add_argument("--daemon", action="store_true", help="Run as a daemon (continuous background process)")
    p.add_argument("--force", action="store_true", help="Force refresh now")
    return p.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Main function for the cron job."""
    args = parse_args(argv)

    # Set defaults from args, or fetches all feeds
    feed_configs = args.feeds or os.environ.get('FEEDS') or None
    refresh_schedule = args.schedule or YorznabClient().Config.Schedule
    next_run = TimezoneAware.now()  # Current time for first run
    download = os.environ.get('DOWNLOAD','false').lower() not in ['false', 'no'] and bool(os.environ.get('DOWNLOAD'))

    # Initialize the cron runner
    CronRunner(feed_configs=feed_configs, refresh_schedule=refresh_schedule, download=download, next_run=next_run)

    # Find feeds that have no database
    feed_missing = [f for f in CronRunner.feed_configs() if not f.exists]

    # Determine whether we need to refresh the feed
    force_msg = HELLO_WORLD
    force_msg = 'Command line argument "--force"' if not force_msg and args.force else force_msg
    force_msg = f"RSS Feed(s) missing: {', '.join(str(f.path) for f in feed_missing)}" if not force_msg and feed_missing else force_msg
    
    LOGGER.info(f"🚀 RSS Refresh Cron initializing")
    if (feed_configs):
        LOGGER.info(f"🔎 Feed config(s): {', '.join(str(f.feed_name) for f in feed_configs)}")
    LOGGER.info(f"⚡ Run now: {force_msg or 'Nope'}")
    if (download):
        LOGGER.info(f"📥 Download top result: {download}")
    LOGGER.info(f"🕐 Schedule: {refresh_schedule}")
    LOGGER.info(f"🌎 Timezone: {TimezoneAware.TIMEZONE_STR}")

    # Force refresh on first run
    if args.force or HELLO_WORLD:
        success = await CronRunner.refresh_rss()
    elif feed_missing:
        success = await CronRunner.refresh_rss(feed_missing)

    if args.daemon:
        # Run as a daemon (continuous background process)
        LOGGER.info("🔄 Running as daemon...")
        try:
            await CronRunner.rss_refresh_cron()
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
