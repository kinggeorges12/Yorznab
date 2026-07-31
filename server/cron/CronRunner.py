from typing import Optional
from threading import Lock
from croniter import croniter
import asyncio
from datetime import datetime, timedelta

# First time message
from server.utils.keystore import KeyStore
HELLO_WORLD = 'This is your first run! Welcome to Yorznab 🤗' if not KeyStore.exists() else None

from server.utils.customlogger import CustomLogger
from server.utils.feedconfig import FeedConfig
from server.utils.timeformatter import TimezoneAware
import asyncio

class CronRunner:

    """
    Class to manage the RSS refresh cron job.
    """
    _instance = None
    _lock = Lock()
    _initialized = False
    _status:str = "Initializing"

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, feed_configs: str, refresh_schedule: str, download: bool, next_run: Optional[datetime]):
        if not self.__class__._initialized:
            self.LOGGER = CustomLogger(name="cron")
            self._feed_configs:str = feed_configs
            self.refresh_schedule:str = refresh_schedule
            self.download:bool = download
            self._next_run:Optional[datetime] = next_run
            self._wakeup_event = asyncio.Event()
            self.__class__._status = "Started"
            self.__class__._initialized = True

    @classmethod
    def status(cls) -> str:
        """Get the current status."""
        return cls._instance._status

    @classmethod
    def next_run(cls) -> Optional[datetime]:
        """Get the next scheduled run time."""
        return cls._instance._next_run

    @classmethod
    def feed_configs(cls) -> list[FeedConfig]:
        """Get the list of feed configurations."""
        return FeedConfig.feeds(values=cls._instance._feed_configs)
    
    @classmethod
    def send_wakeup(cls):
        """Wake up the RSS refresh cron job early."""
        if hasattr(cls._instance, '_wakeup_event'):
            cls._instance._wakeup_event.set()
            cls._instance.LOGGER.info("🔔 RSS refresh wakeup signal sent")

    @classmethod
    async def refresh_rss(cls, feed_configs: list[FeedConfig] | None = None) -> bool:
        """
        Refresh the RSS feed by calling the webhook run_requests function.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        with cls._instance._lock: cls._instance._status = "Running"
        try:
            # Import the webhook module and call run_requests
            from server.routers import webhook
            
            # Call run_requests with no server_type to process both Movies and TV
            run_configs = feed_configs or cls.feed_configs()  # Use all feeds if none specified
            cls._instance.LOGGER.info(f"🔄 Starting RSS refresh: {', '.join([rc.feed_name for rc in run_configs])}")
            
            result = await webhook.run_requests(feed_configs=run_configs)
            
            if result == 0:
                cls._instance.LOGGER.info(f"✅ RSS refresh completed successfully")
                return True
            else:
                cls._instance.LOGGER.error(f"❌ RSS refresh failed with exit code {result}")
                
        except Exception as e:
            cls._instance.LOGGER.error(f"❌ RSS refresh failed with exception: {e}", exc_info=True)

        with cls._instance._lock: cls._instance._status = "Failure"
        return False


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
        
        if base_time is None:
            base_time = TimezoneAware.now()
        
        # Validate and create cron iterator
        if not croniter.is_valid(schedule):
            raise ValueError(f"Invalid cron schedule: {schedule}")
        
        # Get the next run time
        cron = croniter(schedule, start_time=base_time, expand_from_start_time=True)
        next_run = cron.get_next(datetime)
        
        # Ensure the result is timezone-aware
        if next_run.tzinfo is None or next_run.tzinfo.utcoffset(next_run) is None:
            next_run = next_run.replace(tzinfo=TimezoneAware.TIMEZONE)
        
        return next_run

    @classmethod
    async def rss_refresh_cron(cls):
        """
        Background cron job that runs RSS refresh based on cron-like schedule.
        Gets configuration from settings file.
        """

        # Default: every day at random minute/hour
        schedule = cls._instance.refresh_schedule

        cls._instance.LOGGER.info(f"🚀 RSS Refresh Cron Job started (schedule: {schedule})")
        cls._instance.LOGGER.info(f"🌎 Timezone: {TimezoneAware.TIMEZONE_STR}")
        
        while True:
            try:
                feed_configs = cls.feed_configs()
                if feed_configs:
                    cls._instance.LOGGER.info(f"📁 Database file(s): {', '.join(str(f.file) for f in feed_configs)}")
                else:
                    cls._instance.LOGGER.warning("⚠️ No feed configurations found: using default settings")
                    feed_configs = [FeedConfig()]
                need_refresh = []
                max_file_age = 0
                for feed_config in feed_configs:
                    # Check file age in case the cron shut down since last run
                    feed_file_age = feed_config.file_age
                    max_file_age = feed_file_age if feed_file_age > max_file_age else max_file_age
                    
                    # If file doesn't exist, run immediately
                    if feed_file_age == float('inf'):
                        cls._instance.LOGGER.warning("⚠️ Database file doesn't exist - running immediate refresh")
                        need_refresh.append(feed_config)
                if need_refresh:
                    await cls.refresh_rss(feed_configs=need_refresh)
                    # Recheck oldest feed file and continue
                    continue
                
                # Calculate the file's modification time from its age
                now = TimezoneAware.now()
                file_mtime = now - timedelta(seconds=max_file_age)

                # Calculate next run time based on when the file was last modified
                next_run = cls._instance.get_next_run_time(schedule, file_mtime)
                
                # Calculate seconds until next run from current time
                seconds_until_next = (next_run - now).total_seconds()

                # Save next run for front-end
                cls._instance._next_run = next_run
                
                if seconds_until_next > 0:
                    log_time = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
                    cls._instance.LOGGER.info(f"⏰ Next RSS refresh in {seconds_until_next // 60:.0f} minutes at {log_time}")
                    with cls._instance._lock: cls._instance._status =  "Sleeping"

                    try:
                        # Reset the event before waiting
                        cls._instance._wakeup_event.clear()
                        
                        # Wait with timeout using the event
                        await asyncio.wait_for(
                            cls._instance._wakeup_event.wait(),
                            timeout=seconds_until_next
                        )
                        
                        # If we get here, we were woken up early
                        cls._instance.LOGGER.info("🔔 RSS refresh woken up early - recalculating schedule")
                        # Continue loop to recalculate the time
                        continue
                        
                    except asyncio.TimeoutError:
                        cls._instance.LOGGER.debug("⏰ Sleep completed - time to refresh RSS")
                        pass
                else:
                    cls._instance.LOGGER.warning("🔔 Missed an RSS refresh on the schedule - running immediate refresh")

                # Wait for refresh to finish before starting cron timer again
                await cls.refresh_rss()
                    
            except Exception as e:
                cls._instance.LOGGER.error(f"❌ RSS refresh cron job error: {e}", exc_info=True)
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)

