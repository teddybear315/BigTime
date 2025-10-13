import time
from datetime import datetime, timezone

import ntplib
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class NTPWorker(QObject):
    """Background worker that fetches NTP time and emits signals for UI updates.

    Public API:
    - time_updated(str): emitted with YYYY-MM-DD HH:MM:SS on successful sync
    - error(str): emitted on error
    - server_changed(str): slot to change server and perform an immediate fetch
    """

    time_updated = pyqtSignal(str)
    error = pyqtSignal(str)
    server_changed = pyqtSignal(str)

    def __init__(self, ntp_server, interval=1):
        super().__init__()
        self.ntp_server = ntp_server
        self.interval = interval
        self.running = True
        self.server_changed.connect(self.set_server)

    @pyqtSlot(str)
    def set_server(self, server: str):
        if server and isinstance(server, str):
            self.ntp_server = server
            try:
                client = ntplib.NTPClient()
                response = client.request(self.ntp_server, version=3, timeout=0.5)
                dt = datetime.fromtimestamp(response.tx_time, tz=timezone.utc).astimezone()
                self.time_updated.emit(dt.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                self.error.emit("NTP Time: Error")

    def run(self):
        client = ntplib.NTPClient()
        while self.running:
            try:
                response = client.request(self.ntp_server, version=3, timeout=2)
                dt = datetime.fromtimestamp(response.tx_time, tz=timezone.utc).astimezone()
                self.time_updated.emit(dt.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                self.error.emit("NTP Time: Error")
            slept = 0.0
            step = 0.1
            while self.running and slept < self.interval:
                time.sleep(step)
                slept += step
