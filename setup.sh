#!/bin/bash

set -e

# Define output file
output_file="config/settings.yaml"

# Global content array
content=()

# Function to write with delay
write_delay() {
    local message="$1"
    local delay="${2:-10}"
    local no_newline="${3:-false}"
    
    if [ "$no_newline" = "true" ]; then
        printf "%s" "$message"
    else
        printf "%s\n" "$message"
    fi
    sleep 0.01
}

# Function to prompt user
reader_prompt() {
    local message="$1"
    local secure="${2:-false}"
    
    write_delay "$message"
    
    if [ "$secure" = "true" ]; then
        stty -echo
        read input
        stty echo
        echo ""
    else
        read input
        echo ""
    fi
    echo "$input"
}

write_delay ""
write_delay "╭╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╮"
write_delay "╽                                                                              ╽"
write_delay "╿       ██╮   ██╮ ██████╮ ██████╮ ███████╮███╮   ██╮ █████╮ ██████╮ ██╮        ╿"
write_delay "╽       ╰██╮ ██╭╯██╭╼╾╼██╮██╭╼╾██╮╰╼╾███╭╯████╮  ██╽██╭╼╾██╮██╭╼╾██╮██╽        ╽" 100
write_delay "╿        ╰████╭╯ ██╽   ██╽██████╭╯  ███╭╯ ██╭██╮ ██╿███████╿██████╭╯██╿        ╿"
write_delay "╽         ╰██╭╯  ██╿   ██╿██╭╼╾██╮ ███╭╯  ██╽╰██╮██╽██╭╼╾██╽██╭╼╾██╮╰╼╯        ╽"
write_delay "╿          ██╿   ╰██████╭╯██╿  ██╿███████╮██╿ ╰████╿██╿  ██╿██████╭╯██╮        ╿"
write_delay "╽          ╰╼╯    ╰╼╾╼╾╼╯ ╰╼╯  ╰╼╯╰╼╾╼╾╼╾╯╰╼╯  ╰╼╾╼╯╰╼╯  ╰╼╯╰╼╾╼╾╼╯ ╰╼╯        ╽"
write_delay "╟╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╢" 100
write_delay "╿                                                                              ╿"
write_delay "╽ ...a Torznab Indexer that's all YORZ                                         ╽" 2000
write_delay "╿                                                                              ╿"
write_delay "╽              Please fill-in the fields below to get started.                 ╽"
write_delay "╿                                                                              ╿"
write_delay "╰╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╯"
write_delay "" 1000

current_dir="$(pwd)"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
write_delay "Current directory: $current_dir"
if [ "$current_dir" != "$script_dir" ]; then
    write_delay "Script directory: $script_dir"
    input=$(reader_prompt "Are you in the correct directory? yes(Y)/[no(N)]/go(G) ")
    if echo "$input" | grep -qE '^[Gg]$'; then
        cd "$script_dir"
        write_delay "Switching directory: $(pwd)"
    elif ! echo "$input" | grep -qE '^[Yy]$'; then
        write_delay "Cancelling..."
        exit 1
    fi
    write_delay "Continuing..."
fi

# Read existing settings from YAML file
get_setting_value() {
    local section="$1"
    local field="$2"
    local default_value="${3:-}"
    local matched=""
    local in_section=false
    
    for line in "${content[@]}"; do
        if echo "$line" | grep -qE "^${section}:"; then
            in_section=true
            continue
        fi
        if [ "$in_section" = true ] && echo "$line" | grep -qE "^[[:space:]]+${field}:[[:space:]]*(.+)$"; then
            matched="$(echo "$line" | sed -E "s/^[[:space:]]+${field}:[[:space:]]*(.+)$/\1/")"
            break
        fi
        if [ "$in_section" = true ] && echo "$line" | grep -qE '^[^[:space:]]'; then
            in_section=false
        fi
    done
    
    if [ -n "$matched" ]; then
        echo "$(echo "$matched" | xargs)"
    else
        echo "$default_value"
    fi
}

check_for_defaults() {
    local field_name="$1"
    local new_value="$2"
    local default_value="$3"
    local mask="${4:-false}"
    
    if [ -z "$new_value" ] || [ "$new_value" = "" ] || [ "$new_value" = "=" ]; then
        if [ "$mask" = "true" ] && [ -n "$default_value" ]; then
            local masked=""
            i=0
            while [ $i -lt ${#default_value} ]; do
                masked="${masked}*"
                i=$((i + 1))
            done
            echo "  ${field_name}: $masked"
        else
            echo "  ${field_name}: $default_value"
        fi
    elif [ "$new_value" != "-" ]; then
        if [ "$mask" = "true" ] && [ -n "$new_value" ]; then
            local masked=""
            i=0
            while [ $i -lt ${#new_value} ]; do
                masked="${masked}*"
                i=$((i + 1))
            done
            echo "  ${field_name}: $masked"
        else
            echo "  ${field_name}: $new_value"
        fi
    fi
}

write_setting_value() {
    local section="$1"
    local field="$2"
    local new_value="$3"
    local default_value="$4"
    local new_line=""
    local new_content
    local in_section=false
    local field_found=false
    
    # Check for defaults
    if [ -z "$new_value" ] || [ "$new_value" = "" ] || [ "$new_value" = "=" ]; then
        new_line="  ${field}: $default_value"
    elif [ "$new_value" != "-" ]; then
        new_line="  ${field}: $new_value"
    else
        # Return the content unchanged if value is "-"
        echo "${content[@]}"
        return
    fi
    
    for line in "${content[@]}"; do
        if [ "$field_found" = false ]; then
            if echo "$line" | grep -qE "^${section}:"; then
                in_section=true
            elif [ "$in_section" = true ]; then
                if echo "$line" | grep -qE "^[[:space:]]+${field}:"; then
                    field_found=true
                    new_content+=("$new_line")
                    continue
                elif echo "$line" | grep -qE '^[^[:space:]]' && ! echo "$line" | grep -qE "^${section}:"; then
                    if [ "$field_found" = false ]; then
                        new_content+=("$new_line")
                        field_found=true
                    fi
                    in_section=false
                fi
            fi
        fi
        new_content+=("$line")
    done
    
    if [ "$field_found" = false ]; then
        if [ "$in_section" = false ]; then
            new_content+=("${section}:")
        fi
        new_content+=("$new_line")
    fi
    
    echo "${new_content[@]}"
}

# Define output file
output_file="config/settings.yaml"
# Read current settings
if [ -f "$output_file" ]; then
    # POSIX-compatible alternative to mapfile for macOS bash 3.2
    content=""
    while IFS= read -r line; do
        content="$content$line"$'\n'
    done < "$output_file"
    # Convert to array
    IFS=$'\n' read -d '' -r -a content <<< "$content"
else
    content=()
fi

# Get settings from the global content array
r_Url=$(get_setting_value "Radarr" "Url" "http://localhost:7878")
r_ApiKey=$(get_setting_value "Radarr" "ApiKey" "")
r_Endpoint=$(get_setting_value "Radarr" "Endpoint" "/api/v3/movie")

s_Url=$(get_setting_value "Sonarr" "Url" "http://localhost:8989")
s_ApiKey=$(get_setting_value "Sonarr" "ApiKey" "")
s_Endpoint=$(get_setting_value "Sonarr" "Endpoint" "/api/v3/series")

QUrl=$(get_setting_value "qBittorrent" "QUrl" "http://localhost:8080")
QApiKey=$(get_setting_value "qBittorrent" "QApiKey" "")
QUsername=$(get_setting_value "qBittorrent" "QUsername" "")
QPassword=$(get_setting_value "qBittorrent" "QPassword" "")
QEndpoint=$(get_setting_value "qBittorrent" "QEndpoint" "/api/v2")

# Prompt user for inputs
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""
write_delay "To keep current settings, type '=' or just press enter."
write_delay "To delete a setting, type '-' and press enter."
write_delay "Default settings for Endpoints are usually fine for a basic setup."
write_delay "" 1000

write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~          Radarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "??? Lookup the API key for Radarr in: Settings ... General ... Security"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""

input=$(reader_prompt "Url [$r_Url] ")
new_r_Url="$input"
input=$(reader_prompt "ApiKey [${#r_ApiKey} chars] " true)
new_r_ApiKey="$input"
input=$(reader_prompt "Endpoint [$r_Endpoint] ")
new_r_Endpoint="$input"

write_delay ""
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~          Sonarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "??? Lookup the API key for Sonarr in: Settings ... General ... Security"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""

input=$(reader_prompt "Url [$s_Url] ")
new_s_Url="$input"
input=$(reader_prompt "ApiKey [${#s_ApiKey} chars] " true)
new_s_ApiKey="$input"
input=$(reader_prompt "Endpoint [$s_Endpoint] ")
new_s_Endpoint="$input"

write_delay ""
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~        qBittorrent         ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "??? Login settings for qBittorrent are in: [Menu] Tools ... Options ... WebUI"
write_delay "*** Newer versions of qBittorrent allow for API authentication!"
write_delay "*** Enter a dash '-' for the QApiKey if using username/password authentication."
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "%%% Newer versions of qBittorrent allow an API key."
write_delay "%%% If your version does not support it, type a dash '-' and press enter."
write_delay "%%% You must supply a username and password."
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""

input=$(reader_prompt "Url [$QUrl] ")
new_QUrl="$input"
input=$(reader_prompt "ApiKey [${#QApiKey} chars] " true)
new_QApiKey="$input"
if [ "$new_QApiKey" = "-" ]; then
    write_delay "You have chosen to use username/password authentication."
    input=$(reader_prompt "Username [$QUsername] ")
    new_QUsername="$input"
    input=$(reader_prompt "Password [${#QPassword} chars] " true)
    new_QPassword="$input"
else
    new_QUsername=""
    new_QPassword=""
fi
input=$(reader_prompt "Endpoint [$QEndpoint] ")
new_QEndpoint="$input"

print_settings=$(cat <<EOF
### Auto-generated by setup.sh ###

Radarr:
$(check_for_defaults "Url" "$new_r_Url" "$r_Url")
$(check_for_defaults "ApiKey" "$new_r_ApiKey" "$r_ApiKey" true)
$(check_for_defaults "Endpoint" "$new_r_Endpoint" "$r_Endpoint")
Sonarr:
$(check_for_defaults "Url" "$new_s_Url" "$s_Url")
$(check_for_defaults "ApiKey" "$new_s_ApiKey" "$s_ApiKey" true)
$(check_for_defaults "Endpoint" "$new_s_Endpoint" "$s_Endpoint")
qBittorrent:
$(check_for_defaults "QUrl" "$new_QUrl" "$QUrl")
$(check_for_defaults "QApiKey" "$new_QApiKey" "$QApiKey" true)
$(check_for_defaults "QUsername" "$new_QUsername" "$QUsername")
$(check_for_defaults "QPassword" "$new_QPassword" "$QPassword" true)
$(check_for_defaults "QEndpoint" "$new_QEndpoint" "$QEndpoint")
EOF
)

write_delay ""
write_delay "$print_settings"
write_delay ""

# Update content array
content=($(write_setting_value "Radarr" "Url" "$new_r_Url" "$r_Url"))
content=($(write_setting_value "Radarr" "ApiKey" "$new_r_ApiKey" "$r_ApiKey"))
content=($(write_setting_value "Radarr" "Endpoint" "$new_r_Endpoint" "$r_Endpoint"))

content=($(write_setting_value "Sonarr" "Url" "$new_s_Url" "$s_Url"))
content=($(write_setting_value "Sonarr" "ApiKey" "$new_s_ApiKey" "$s_ApiKey"))
content=($(write_setting_value "Sonarr" "Endpoint" "$new_s_Endpoint" "$s_Endpoint"))

content=($(write_setting_value "qBittorrent" "QUrl" "$new_QUrl" "$QUrl"))
content=($(write_setting_value "qBittorrent" "QApiKey" "$new_QApiKey" "$QApiKey"))
content=($(write_setting_value "qBittorrent" "QUsername" "$new_QUsername" "$QUsername"))
content=($(write_setting_value "qBittorrent" "QPassword" "$new_QPassword" "$QPassword"))
content=($(write_setting_value "qBittorrent" "QEndpoint" "$new_QEndpoint" "$QEndpoint"))

write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
if [ -f "$output_file" ]; then
    datetime=$(date +%Y%m%d_%H%M%S)
    output_file_bak="$output_file-$datetime.bak"
    mv "$output_file" "$output_file_bak"
    write_delay "~~~ Moving old settings file:  $output_file_bak"
fi
write_delay "~~~ Writing settings to file: $output_file"
printf "%s\n" "${content[@]}" > "$output_file"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""
write_delay "Done!"
write_delay "Reloading configuration..." 1000

exit 0