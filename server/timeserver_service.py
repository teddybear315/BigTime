"""
Time Server Service for BigTime Server
Provides accurate time synchronization with timezone support and automatic timeserver selection.
"""

import threading
import time
import zoneinfo
from datetime import datetime, timezone
from typing import Dict, Optional

from shared.logging_config import get_server_logger

try:
    import ntplib
except ImportError:
    ntplib = None


class TimeServerService:
    """Manages time synchronization for the BigTime server"""

    # Timezone to NTP server mapping for optimal performance
    TIMEZONE_SERVERS = {
        # North America
        'America/New_York': ['time.nist.gov', 'pool.ntp.org', 'time.cloudflare.com'],
        'America/Chicago': ['time.nist.gov', 'pool.ntp.org', 'time.cloudflare.com'],
        'America/Denver': ['time.nist.gov', 'pool.ntp.org', 'time.cloudflare.com'],
        'America/Los_Angeles': ['time.nist.gov', 'pool.ntp.org', 'time.cloudflare.com'],

        # Europe
        'Europe/London': ['uk.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Europe/Paris': ['fr.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Europe/Berlin': ['de.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Europe/Amsterdam': ['nl.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],

        # Asia Pacific
        'Asia/Tokyo': ['jp.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Asia/Shanghai': ['cn.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Asia/Singapore': ['sg.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],
        'Australia/Sydney': ['au.pool.ntp.org', 'pool.ntp.org', 'time.cloudflare.com'],

        # Default/Global
        'UTC': ['pool.ntp.org', 'time.cloudflare.com', 'time.google.com'],
    }

    def __init__(self, timezone_name: str = 'UTC', sync_interval: int = 60):
        self.logger = get_server_logger()
        self.timezone_name = timezone_name
        self.sync_interval = sync_interval
        self.running = False
        self.sync_thread = None
        self.last_sync_time = None
        self.sync_offset = 0.0  # Offset from system time
        self.current_server = None
        self.sync_callbacks = []

        # Get appropriate servers for timezone
        self.ntp_servers = self.get_servers_for_timezone(timezone_name)

        if ntplib is None:
            self.logger.warning("ntplib not available. Time sync disabled.")

    def get_servers_for_timezone(self, tz_name: str) -> list:
        """Get the best NTP servers for a given timezone"""
        if tz_name in self.TIMEZONE_SERVERS:
            return self.TIMEZONE_SERVERS[tz_name].copy()

        # Try to find a regional server based on timezone
        if '/' in tz_name:
            continent = tz_name.split('/')[0]

            if continent == 'America':
                return self.TIMEZONE_SERVERS['America/New_York'].copy()
            elif continent == 'Europe':
                return self.TIMEZONE_SERVERS['Europe/London'].copy()
            elif continent == 'Asia':
                return self.TIMEZONE_SERVERS['Asia/Tokyo'].copy()
            elif continent == 'Australia':
                return self.TIMEZONE_SERVERS['Australia/Sydney'].copy()

        # Default to global servers
        return self.TIMEZONE_SERVERS['UTC'].copy()

    def add_sync_callback(self, callback):
        """Add a callback to be called when time is synchronized"""
        self.sync_callbacks.append(callback)

    def remove_sync_callback(self, callback):
        """Remove a sync callback"""
        if callback in self.sync_callbacks:
            self.sync_callbacks.remove(callback)

    def sync_time_once(self) -> Optional[Dict]:
        """Perform a single time sync and return result"""
        if ntplib is None:
            return {'error': 'ntplib not available'}

        for server in self.ntp_servers:
            try:
                client = ntplib.NTPClient()
                response = client.request(server, version=3, timeout=2)

                # Calculate offset from system time
                ntp_time = response.tx_time
                system_time = time.time()
                self.sync_offset = ntp_time - system_time

                self.current_server = server
                self.last_sync_time = datetime.now(timezone.utc)

                # Convert to timezone with fallback
                try:
                    tz = zoneinfo.ZoneInfo(self.timezone_name)
                    synced_datetime = datetime.fromtimestamp(ntp_time, tz=tz)
                except Exception:
                    # Fallback to UTC if timezone data is missing
                    tz = timezone.utc
                    synced_datetime = datetime.fromtimestamp(ntp_time, tz=tz)
                    if self.timezone_name != 'UTC':
                        self.logger.warning(f"Timezone '{self.timezone_name}' not available, using UTC")

                result = {
                    'success': True,
                    'server': server,
                    'offset': self.sync_offset,
                    'synced_time': synced_datetime,
                    'formatted_time': synced_datetime.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'sync_timestamp': self.last_sync_time
                }

                # Call callbacks
                for callback in self.sync_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        self.logger.error(f"Sync callback error: {e}")

                return result

            except Exception as e:
                self.logger.warning(f"Failed to sync with {server}: {e}")
                continue

        return {'error': 'All NTP servers failed'}

    def get_current_time(self) -> datetime:
        """Get current time with NTP correction applied"""
        try:
            tz = zoneinfo.ZoneInfo(self.timezone_name)
        except Exception:
            # Fallback to UTC if timezone data is missing
            tz = timezone.utc

        if self.sync_offset != 0.0:
            # Apply NTP correction
            corrected_timestamp = time.time() + self.sync_offset
            return datetime.fromtimestamp(corrected_timestamp, tz=tz)
        else:
            # Fallback to system time
            return datetime.now(tz)

    def start_sync_service(self):
        """Start the background time sync service"""
        if self.running or ntplib is None:
            return

        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()

        self.logger.info(f"Time sync service started with {self.timezone_name} timezone")
        self.logger.info(f"Using NTP servers: {', '.join(self.ntp_servers)}")

    def stop_sync_service(self):
        """Stop the background time sync service"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=1)

    def _sync_loop(self):
        """Background sync loop"""
        while self.running:
            result = self.sync_time_once()

            if result and 'success' in result:
                self.logger.info(f"Time synced with {result['server']}: {result['formatted_time']}")
            elif result and 'error' in result:
                self.logger.warning(f"Time sync failed: {result['error']}")

            # Wait for next sync
            elapsed = 0
            while elapsed < self.sync_interval and self.running:
                time.sleep(0.1)
                elapsed += 0.1

    def update_timezone(self, new_timezone: str):
        """Update the timezone and refresh server list"""
        self.timezone_name = new_timezone
        self.ntp_servers = self.get_servers_for_timezone(new_timezone)
        self.logger.info(f"Timezone updated to {new_timezone}")

    def update_sync_interval(self, new_interval: int):
        """Update sync interval"""
        self.sync_interval = max(1, new_interval)  # Minimum 1 second
        self.logger.info(f"Sync interval updated to {self.sync_interval}s")

    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        return {
            'timezone': self.timezone_name,
            'current_server': self.current_server,
            'last_sync': self.last_sync_time,
            'sync_offset': self.sync_offset,
            'sync_interval': self.sync_interval,
            'running': self.running,
            'current_time': self.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')
        }


# Global time service instance
_time_service = None


def get_time_service() -> TimeServerService:
    """Get the global time service instance"""
    global _time_service
    if _time_service is None:
        _time_service = TimeServerService()
    return _time_service


def initialize_time_service(timezone_name: str = 'UTC', sync_interval: int = 5, start: bool = True):
    """Initialize the global time service

    Only initializes once. Subsequent calls are ignored to prevent overwriting
    a running time service.

    Args:
        timezone_name: Timezone for the service
        sync_interval: Seconds between sync attempts
        start: If True, start the sync service immediately. If False, it must be started manually.
    """
    global _time_service
    if _time_service is not None:
        # Already initialized, don't overwrite
        return _time_service

    return _time_service
