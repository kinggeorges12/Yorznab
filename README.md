# Yorznab
Ever wanted to make your own Torznab server of your own? Now you can!

Welcome to Yorznab, the best way to connect your Radarr and Sonarr apps to download clients without a Usenet or Torznab subscription. Connect Seerr \(Jellyseerr\) to automatically search for requested content through qBittorrent and publish a Yorznab RSS feed. Radarr and Sonarr use the Yorznab RSS feed to find and request torrents from supported download clients like qBittorrent.

# Requirements
Compatible with Linux or Windows. Requires the following services to fully use this app. Current tested configuration:

- Ubuntu v26
- Docker v29
- [Seerr](https://github.com/seerr-team/seerr) v3 configured with Radarr and Sonarr
- [Radarr](https://github.com/Radarr/Radarr) v6 configured with a download client
- [Sonarr](https://github.com/sonarr/sonarr) v4 configured with a download client
- [qBittorrent](https://github.com/qbittorrent/qBittorrent) v5
- [Jackett](https://github.com/Jackett/Jackett) v\.24 \(optional\)

# Install
These instructions will setup the Python app on your localhost in Docker. There is no GUI for this app, so you must use the browser to view the outputs.

Use the scripts below to download and install. Manually download by clicking `Code > Download Zip` on this page. Manually install by unzipping into your Docker folder.

## Linux
```
sudo mkdir -p /srv/dev/yorznab/app
cd /srv/dev/yorznab
sudo chown -R $(id -un):$(id -gn) .
wget -O yorznab-main.tar.gz https://github.com/kinggeorges12/Yorznab/archive/refs/heads/main.tar.gz
tar --strip-components=1 -xvzf yorznab-main.tar.gz -C ./app
cp --update=none ./app/config/filters.yaml.sample ./app/config/filters.yaml # Recommended
```

## Windows
```
New-Item -Path C:\Docker\yorznab -ItemType Directory -Force
Set-Location C:\Docker\yorznab
Invoke-WebRequest -Uri "https://github.com/kinggeorges12/Yorznab/archive/refs/heads/main.zip" -OutFile "yorznab-main.zip"
Expand-Archive -Path "yorznab-main.zip" -DestinationPath $env:TEMP
Get-ChildItem "$env:TEMP\yorznab-main\" -Force | Move-Item -Destination .
Copy-Item -Confirm -Path ./app/config/filters.yaml.sample -Destination ./app/config/filters.yaml.sample
```

# Setup API Keys

Fill-in this information in `settings.yaml` using the automated setup tool. Instructions for each app are found in the subsections below.
- \[Linux Shell\] `cd /srv/dev/yorznab/app && sudo chmod +x setup.sh && ./setup.sh`
- \[Windows PowerShell\] `cd C:\Docker\yorznab && ./setup.ps1`

## Radarr/Sonarr
This allows Yorznab to pull lists of Wanted items from Sonarr and Radarr.

1. Open Radarr or Sonarr in your browser.
2. Go to **Settings → General → Security**.
3. Copy the **API Key** to `ApiKey` under the Radarr or Sonarr entry.

## qBittorrent
This allows Yorznab to query the qBittorrent search engine.

1. Open qBittorrent WebUI in your browser.
2. Go to **Settings → WebUI → Authentication**.
3. Copy the **API Key** (`qbt_...`).
4. If the qBittorrent version does not have API Key option, provide the `QUsername` and `QPassword` and DO NOT include the QApiKey.

# Docker
This starts the service in Docker. You must follow steps in external apps to make it work.

1. Open shell and enter the Docker directory:
    - \[Linux Shell\] `cd /srv/dev/yorznab`
    - \[Windows PowerShell\] `cd C:\Docker\yorznab`
2. Create the data for Yorznab extract and home directory to persist Python files \[optional\]:
    - \[Linux Shell\] `mkdir -p home export python && sudo chown -R $(id -un):$(id -gn) .`
3. Run Docker file: `docker compose -f ./app/docker-compose.yml up -d`

# Indexer
This allows Radarr and Sonarr to query Yorznab for torrents. The settings for `API_KEY` and `FEED_KEY` are randomly generated when Yorznab starts in Docker and stored in `config/keys.yaml`.

1. Open Radarr or Sonarr in your browser.
2. Go to **Settings → Indexers → + → Torznab**.
3. Click the gear at the bottom of the settings page to show advanced settings.
4. Fill-in these settings, using values from `config/yorznab.yaml`` in parentheses:
    - Name: Yorznab
    - Enable RSS: ✅
    - Enable Automatic Search: ✅
    - Enable Interactive Search: ✅
    - URL (feed: link): http://localhost:9118
    - API Path (feed: api_endpoint): /api
    - API Key (API_KEY): YOUR_API_KEY
    - \[RADARR\] Categories: ✅ Movies \(all\)
    - \[SONARR\] Categories: ✅ TV \(all except 🔲 Anime\)
    - \[SONARR\] Anime Categories: 🔲TV > ✅ Anime \(only\)
    - \[SONARR\] Anime Standard Format Search: ✅
    - Minimum Seeders: 1 *recommended*
    - Seed Ratio, Seed Time, Season-Pack Seed Time: see \(Tracker Tags\)[https://github.com/kinggeorges12/Yorznab#tracker-tags]
    - Reject Blocklisted Torrent Hashes While Grabbing: ✅
    - Indexer Priority: 25 *default*
    - \[SONARR\] Maximum Single Episode Age: 730 (any day after will grab season packs)

# Webhook
This allows Seerr to notify Yorznab when new content is requested.

1. Open Seerr in your browser.
2. Go to **Settings → Notifications → Webhook**.
3. Fill-in these settings, using values from `config/yorznab.yaml`` in parentheses:
    - Enable Agent: Yorznab: ✅
    - Support URL Variables: 🔲
    - Webhook URL (feed: link/webhook_endpoint): http://localhost:9118/webhook
    - Authorization Header \(WEBHOOK_KEY\): YOUR_WEBHOOK_KEY
    - JSON Payload: *do not change default*
    - Notification Types \(🔲 Others\):
        - ✅ Request Automatically Approved
        - ✅ Request Approved

# Filters
The default qBittorrent search engine is built for manual intervention. Implement filters to allow for more automation-friendly search results. By default, the sample is applied when you setup Yorznab. Explore the sample filter and read instructions in [filters.yaml.sample](config/filters.yaml.sample).

Turn off the filter by removing the file in `/app/config/filters.yaml`.

## Tags
Private trackers often have seeding requirements. You can use tags in qBittorrent to separate these from public trackers. Simply setup your TrackerTags section in `config/filter.yaml` for your private trackers.
```
# Only output torrents matching TrackerTags entries below
tracker_tags_only: false
# Add tags in qBittorrent to downloads from these trackers
tracker_tags:
  Private Tracker Name 1: privatetracker1.com
  Private Tracker Name 2: privatetracker2.com
  Private Tracker Name 3: privatetracker3.com
```

If you need to provide special seeding requirements for trackers, be sure to set the `tracker_tags_only: true`
1. Create another instance of Yorznab (e.g., PrivateYorznab) for each indexer seed requirements.
2. Include each indexer in Radarr and Sonarr using the instructions in [Create Indexer](#create-indexer)
3. Apply rules in Sonarr to continue seeding after downloading.

## Jackett
Yorznab looks for Jackett tags in search results automatically. The brackets in search results indicate the tracker, e.g., \[Tracker\] torrent. Use the flag `remove_jackett_tags` to removes those bracketed trackers from the filename.

# Development
Setup the local Python environment for running locally without Docker.

1. Install [Python](https://www.python.org/downloads/) \(test on 3.11+\) on your server or PC. Ensure this is available in your shell: `python --version`
2. Run the following commands for your OS:
    - \[Linux Shell\] `cd /srv/dev/yorznab/app && sudo chmod +x build.sh run.sh setup.sh && ./run.sh`
    - \[Windows PowerShell\] `Set-Location C:\Docker\yorznab\app && ./build.ps1 && ./run.ps1`
3. Visit https://localhost:9118/status

# AI Disclosure
What you're reading on this page was not written by AI. I wrote the Torznab code for this in 2025 without AI, or even an IDE. Mostly done through looking up the endpoints available for the protocol. I used AI to generate the front-end web server. I also regenerated my utility files with AI to accomodate yaml files.

# Copyright Notice
Please follow applicable copyright laws for your country and the [GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies).
