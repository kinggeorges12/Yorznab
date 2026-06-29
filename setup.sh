#!/bin/bash

set -e

skip=""
key=0
echo
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "║                                                                              ║"
echo "║       ██╗   ██╗ ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██████╗ ██╗        ║"
echo "║       ╚██╗ ██╔╝██╔═══██╗██╔══██╗╚══███╔╝████╗  ██║██╔══██╗██╔══██╗██║        ║"
echo "║        ╚████╔╝ ██║   ██║██████╔╝  ███╔╝ ██╔██╗ ██║███████║██████╔╝██║        ║"
if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "║         ╚██╔╝  ██║   ██║██╔══██╗ ███╔╝  ██║╚██╗██║██╔══██║██╔══██╗╚═╝        ║"
if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "║          ██║   ╚██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║██████╔╝██╗        ║"
echo "║          ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═════╝ ╚═╝        ║"
echo "║══════════════════════════════════════════════════════════════════════════════║"
echo "║                                                                              ║"
echo "║                                         ...a Torznab Indexer that's all YORZ ║"
echo "║                                                                              ║"
if [ "$skip" = "" ]; then read -t 2 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "║══════════════════════════════════════════════════════════════════════════════║"
echo "║                                                                              ║"
echo "║              Please fill-in the fields below to get started.                 ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo
if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;

# Define output file
output_file="config/settings.yaml"

current_dir="$PWD"
script_dir="$(cd "$(dirname "$0")" && pwd)"
if [ "$current_dir" != "$script_dir" ]; then
    echo "Install: $script_dir"
    echo "Current: $current_dir"
    read -p "Are you in the correct directory? yes(Y)/[no(N)]/go(G) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Gg]$ ]]; then
        cd "$script_dir"
        echo "Switching directory: $PWD"
    elif [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelling..."
        exit 1
    fi
    echo "Continuing..."
fi

if [ -f "$output_file" ]; then
    echo "It looks like the settings file was already created."
    read -p "Do you want to (O)verwrite some values or (K)eep it the way it is? " -n 1 -r
    echo
    if [[ $REPLY = "" ]]; then
        echo "Alright, hang on!"
    elif [[ ! $REPLY =~ ^[Oo]$ ]]; then
        echo "Keeping it the way it is... Bye!"
        exit 1
    fi
    echo "Continuing..."

    r_Url=$(sed -n '/^Radarr:/,/^[^ ]/ { /^  Url: +/ s/^  Url: //p }' config/settings.yaml)
    r_ApiKey=$(sed -n '/^Radarr:/,/^[^ ]/ { /^  ApiKey: +/ s/^  ApiKey: //p }' config/settings.yaml)
    r_Endpoint=$(sed -n '/^Radarr:/,/^[^ ]/ { /^  Endpoint: +/ s/^  Endpoint: //p }' config/settings.yaml)
    s_Url=$(sed -n '/^Sonarr:/,/^[^ ]/ { /^  Url: +/ s/^  Url: //p }' config/settings.yaml)
    s_ApiKey=$(sed -n '/^Sonarr:/,/^[^ ]/ { /^  ApiKey: +/ s/^  ApiKey: //p }' config/settings.yaml)
    s_Endpoint=$(sed -n '/^Sonarr:/,/^[^ ]/ { /^  Endpoint: +/ s/^  Endpoint: //p }' config/settings.yaml)
    QUrl=$(sed -n '/^qBittorrent:/,/^[^ ]/ { /^  QUrl: +/ s/^  QUrl: //p }' config/settings.yaml)
    QApiKey=$(sed -n '/^qBittorrent:/,/^[^ ]/ { /^  QApiKey: +/ s/^  QApiKey: //p }' config/settings.yaml)
    QUsername=$(sed -n '/^qBittorrent:/,/^[^ ]/ { /^  QUsername: +/ s/^  QUsername: //p }' config/settings.yaml)
    QPassword=$(sed -n '/^qBittorrent:/,/^[^ ]/ { /^  QPassword: +/ s/^  QPassword: //p }' config/settings.yaml)
    QEndpoint=$(sed -n '/^qBittorrent:/,/^[^ ]/ { /^  QEndpoint: +/ s/^  QEndpoint: //p }' config/settings.yaml)

fi

if [ -z "$r_Url" ]; then
    r_Url="http://localhost:7878"
fi
if [ -z "$r_Endpoint" ]; then
    r_Endpoint="/api/v3/movie"
fi
if [ -z "$s_Url" ]; then
    s_Url="http://localhost:8989"
fi
if [ -z "$s_Endpoint" ]; then
    s_Endpoint="/api/v3/series"
fi
if [ -z "$QUrl" ]; then
    QUrl="http://localhost:8080"
fi
if [ -z "$QEndpoint" ]; then
    QEndpoint="/api/v2"
fi

read_password() {
    local password=""
    local char

    stty -echo

    while IFS= read -rsn1 char; do
        case "$char" in
            "")
                # Enter
                break
                ;;
            $'\177'|$'\b')
                if [[ -n $password ]]; then
                    password=${password%?}
                    printf '\b \b'
                fi
                ;;
            *)
                password+="$char"
                printf '*'
                ;;
        esac
    done

    stty echo
    printf '\n'
    REPLY=$password
}

# Prompt user for inputs
echo
echo
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo
echo "To keep current settings, press enter."
echo "To delete a setting, type '-' and press enter."
echo "Default settings for Endpoints are usually find for a basic setup."
echo

skip=""; key=0; if [ "$skip" = "" ]; then read -t 2 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~          Radarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo
echo ">>> Lookup the API key for Radarr in: Settings > General > Security"
echo
read -p "URL (current: $r_Url): " new_r_Url
echo -n "API Key (current: ${#r_ApiKey} chars): "
read_password && new_r_ApiKey="$REPLY"
read -p "Endpoint (current: $r_Endpoint): " new_r_Endpoint

echo
skip=""; key=0; if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~          Sonarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo
echo ">>> Lookup the API key for Sonarr in: Settings > General > Security"
echo
read -p "URL (current: $s_Url): " new_s_Url
echo -n "API Key (current: ${#s_ApiKey} chars): "
read_password && new_s_ApiKey="$REPLY"
read -p "Endpoint (current: $s_Endpoint): " new_s_Endpoint

echo
skip=""; key=0; if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~        qBittorrent         ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo
echo ">>> Login settings for qBittorrent are in: [Menu] Tools > Options > WebUI"
echo "*** Newer versions of qBittorrent allow for API authentication!"
echo "*** Enter a dash '-' for the QApiKey if using username/password authentication."
echo
echo "Newer versions of qBittorrent allow an API key."
echo "If your version does not support it, type a dash '-' and press enter."
echo "You must supply a username and password."
echo
read -p "URL (current: $QUrl): " new_QUrl
echo -n "API Key (current: ${#QApiKey} chars): "
read_password && new_QApiKey="$REPLY"
read -p "Username (current: $QUsername): " new_QUsername
echo -n "Password (current: ${#QPassword} chars): "
read_password && new_QPassword="$REPLY"
read -p "Endpoint (current: $QEndpoint): " new_QEndpoint
echo

check_for_dash() {
    local field_name="$1"
    local new_value="$2"
    local default_value="$3"

    if [ -z "$new_value" ]; then
        echo "  $field_name: $default_value" >> "$output_file"
    elif [ "$new_value" != "-" ]; then
        echo "  $field_name: $new_value" >> "$output_file"
    fi
}

echo -n > "$output_file"
# Write inputs to file with a timestamp
echo "### Auto-generated by setup.sh ###" >> "$output_file"
echo >> "$output_file"
echo "Radarr:" >> "$output_file"
check_for_dash "URL" "$new_r_Url" "$r_Url"
check_for_dash "API Key" "$new_r_ApiKey" "$r_ApiKey"
check_for_dash "Endpoint" "$new_r_Endpoint" "$r_Endpoint"
echo "Sonarr:" >> "$output_file"
check_for_dash "URL" "$new_s_Url" "$s_Url"
check_for_dash "API Key" "$new_s_ApiKey" "$s_ApiKey"
check_for_dash "Endpoint" "$new_s_Endpoint" "$s_Endpoint"
echo "qBittorrent:" >> "$output_file"
check_for_dash "URL" "$new_QUrl" "$QUrl"
check_for_dash "API Key" "$new_QApiKey" "$QApiKey"
check_for_dash "Username" "$new_QUsername" "$QUsername"
check_for_dash "Password" "$new_QPassword" "$QPassword"
check_for_dash "Endpoint" "$new_QEndpoint" "$QEndpoint"
echo
echo "Settings written to: $output_file"
echo "Until next time, enjoy YOR very own Yorznab!"
skip=""; key=0; if [ "$skip" = "" ]; then read -t 1 -n 1 -s key && skip=1 || { [ -n "$key" ] && skip=1; } ; fi;
echo 