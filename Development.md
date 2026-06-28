DONE in QBit watchdog: Automatically delete failed downloads in qbit and blacklist the torrent files.

move config files to config folder: in settings.yaml, change Movies to Radarr, Shows to Sonarr. Proper names and endpoints should be defaulted to those values in the file. Rename "Trackers" to "PrivateTrackers" and rename other settings so they make sense.

Set higher priority to more recent files

Sonarr yorznab check next episode for tracked and continuing shows.

immediately post updates to torrent file after finding suitable torrents. Run this as a singleton task with a queue that runs async to the script.

Add data and config folders to .gitignore

Add installation instructions like the webhook setup for Arrs.

Add installation instructions for blocking bad torrent files in qbit.

Create web interface for app.

Automatically run installation instructions with auto-setup enabled.