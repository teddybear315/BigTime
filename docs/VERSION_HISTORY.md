# BigTime Version Tracker

### Version 2.1.2 (Current - December 17, 2025)
**Release Summary**: Maintenance update with DB safety checks, modularized dialogs, enhanced backup/migration tooling, and refreshed docs.
- ✅ **Server Reliability**: Startup integrity check with repair attempt, rollback journaling for simpler concurrency, deferred time-service start after server boot, and stricter API-key auth (active flag enforcement, clearer diagnostics, safer defaults).
- ✅ **UI/UX Improvements**: Legacy monolithic dialog module replaced by modular `ui/dialogs/*`; shared dialogs add database selection flows for backup/migration; client dialogs kept feature parity within the new structure.
- ✅ **Backups & Migration**: Backup utilities can create timestamped backups from arbitrary source paths; migration flows surfaced via new dialogs and documented in the Database Migration Guide.
- ✅ **Documentation**: Added Quick Start and Migration guides; added this file, updated API, Setup, and Troubleshooting docs to reflect current behavior and packaging notes.
- ✅ **Packaging**: Updated Win11/macOS distribution archives and asset alignment for current builds; interim binaries refreshed.
- ✅ **Commit Reference**: v2.1.2 commit by Logan Houston on December 17, 2025.

### Version 2.1.1 (December 11, 2025)
**Release Summary**: Stability/UX maintenance release focusing on graceful shutdowns, clearer configuration dialogs, and refreshed documentation.
- ✅ **Server & Tray**: Improved shutdown pathway via admin endpoint with better connection-error handling; tray manager now passes the QApplication instance explicitly and keeps emits/states aligned during stop/start.
- ✅ **UI/UX Improvements**: Settings dialogs surface version details for clearer support/debug visibility; minor UI cleanups in shared dialogs module.
- ✅ **Documentation**: README, API reference, setup, and troubleshooting guides updated to reflect current behavior and guidance.
- ✅ **Packaging & Assets**: Updated macOS/Windows distribution archives and ignored paths; small dependency/asset alignment tweaks.
- ✅ **Commit Reference**: v2.1.1 commit by Logan Houston on December 11, 2025.

### Version 2.1.0 (December 9, 2025)
**Release Summary**: Major code cleanup and reliability pass for the offline-first client/server stack, plus refreshed platform-specific build outputs.
- ✅ **Client Sync & Startup**: Background inbound sync and connection checks run in separate threads to keep the UI responsive; enhanced log repair/reset flow leverages centralized db helpers and backoff-aware timers; faster startup via a minimal loading UI before heavy initialization.
- ✅ **UI & Dialogs**: Added a multi-log editor dialog with timezone-aware clock-in/out editing, inline validation, and “still clocked in” handling to simplify corrections.
- ✅ **Server & Tray**: System tray app now verifies platform tray availability, starts the Waitress-backed server in a managed thread, and attempts graceful shutdown through the admin endpoint with fallbacks.
- ✅ **Data & Backups**: Introduced shared backup utilities for timestamped database backups and restores; database helpers gained stricter validation, WAL/busy-timeout defaults, and shared row-to-model converters.
- ✅ **Packaging & Builds**: Added separate Windows/macOS PyInstaller specs (`BigTime-Client-w.spec`, `BigTime-Client-m.spec`, `BigTime-Server-w.spec`, `BigTime-Server-m.spec`), refreshed Win11 executables/shortcuts, and aligned dependency listings.
- ✅ **Commit Reference**: v2.1.0 commit by Logan Houston on December 9, 2025.

### Version 2.0 (October 14, 2025)
**Release Summary**: First BigTime release with a Waitress-backed REST server, PyQt6 desktop client, and offline-first synchronization for multi-device setups.
- ✅ **Client Application**: New PyQt6 GUI stack (`gui_app.py`, `dialog_managers.py`, `background_worker.py`, `timeclock_client.py`) plus `RemoteSyncService` for push/pull sync, conflict resolution, backoff handling, and live connection status signals.
- ✅ **Server Application**: Flask API with CORS, SQLite WAL configuration, API key support, and a time service; includes tray launcher (`server_tray.py`) and PyInstaller spec for Waitress packaging.
- ✅ **Shared/Data Layer**: Added shared models, logging configuration, and database helpers defining employee and time log schemas with device/client identifiers; standardized datetime formatting utilities.
- ✅ **UI Updates**: Reworked dialog set and fonts, removed the legacy `ui/app.py`, and refreshed error handling and setup flows across the client interface.
- ✅ **Documentation & Tooling**: Added API, setup, and troubleshooting guides; new launcher entry point and cleanup script; requirements updated; PyInstaller specs and Windows distribution shortcuts/executables included.
- ✅ **Commit Reference**: v2.0 update commit by Logan Houston on October 14, 2025.

### Version 1.0 (SmallTime)

Please see my SmallTime repo for a single-machine solution. This app is an extension of it. No future updates are planned for SmallTime unless requested so feel free to ask for parity updates with BigTime design and features.
