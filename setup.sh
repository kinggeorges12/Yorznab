#!/bin/bash
export LANG=en_US.UTF-8

error_trap() {
    local line=$1
    local command=$2
    local code=$3
    echo "ERROR: Command '$command' failed with exit code $code at line $line" >&2
    echo "Script: $0" >&2
    echo "Stack trace:" >&2
    local i=0
    while caller $i; do
        i=$((i+1))
    done
    exit $code
}

trap 'error_trap $LINENO "$BASH_COMMAND" $?' ERR

set -e

# Define output file
output_file="config/settings.yaml"

# Global content array
content=()

# Function to write with delay
write_delay() {
    local message="$1"
    local delay="${2:-10}"
    local no_newline="${3:-}"
    
    if [ -n "$no_newline" ]; then
        printf "%s" "$message"
    else
        printf "%s\n" "$message"
    fi
    sleep "$((delay / 1000)).$((delay % 1000))"
}

write_mask() {
    local count="$1"
    local i=0
    while [ $i -lt "$count" ]; do
        printf "*"
        i=$((i + 1))
    done
    printf "\n"
}

# Function to read input
read_input() {
    local secure="${1:-}"
    local input=""
    
    if [ -n "$secure" ]; then
        read -s input || true
    else
        read input || true
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
write_delay "╽       ...a Torznab Indexer that's all YORZ                                   ╽" 2000
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
    write_delay "Are you in the correct directory? yes(Y)/[no(N)]/go(G) "
    input=$(read_input)
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
    local line=""
    
    for line in "${content[@]}"; do
        line="${line//$'\r'/}"
        
        if [[ "$line" =~ ^${section}: ]]; then
            in_section=true
            continue
        fi
        
        if [ "$in_section" = true ]; then
            if [[ "$line" =~ ^[^[:space:]] ]]; then
                in_section=false
                continue
            fi
            
            if [[ "$line" =~ ^[[:space:]]+${field}:[[:space:]]*(.+)$ ]]; then
                matched="${BASH_REMATCH[1]}"
                matched="${matched#"${matched%%[![:space:]]*}"}"
                matched="${matched%"${matched##*[![:space:]]}"}"
                break
            fi
        fi
    done
    
    echo "${matched:-$default_value}"
}

check_for_defaults() {
    local field_name="$1"
    local new_value="$2"
    local default_value="$3"
    local mask="${4:-false}"
    
    if [ -z "$new_value" ] || [ "$new_value" = "" ] || [ "$new_value" = "=" ]; then
        if [ "$mask" = "true" ] && [ -n "$default_value" ]; then
            echo "  ${field_name}: $(write_mask ${#default_value})"
        else
            echo "  ${field_name}: $default_value"
        fi
    elif [ "$new_value" != "-" ]; then
        if [ "$mask" = "true" ] && [ -n "$new_value" ]; then
            echo "  ${field_name}: $(write_mask ${#new_value})"
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
    local new_content=()
    local in_section=false
    local field_found=false
    local line=""
    
    if [ -z "$new_value" ] || [ "$new_value" = "" ] || [ "$new_value" = "=" ]; then
        new_line="  ${field}: $default_value"
    elif [ "$new_value" != "-" ]; then
        new_line="  ${field}: $new_value"
    else
        return
    fi
    
    for line in "${content[@]}"; do
        if [ "$field_found" = false ]; then
            if [[ "$line" =~ ^${section}: ]]; then
                in_section=true
            elif [ "$in_section" = true ]; then
                if [[ "$line" =~ ^[[:space:]]+${field}: ]]; then
                    field_found=true
                    new_content+=("$new_line")
                    continue
                elif [[ "$line" =~ ^[^[:space:]] ]] && [[ ! "$line" =~ ^${section}: ]]; then
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
    
    content=("${new_content[@]}")
}

# Define output file
output_file="config/settings.yaml"
# Read current settings
if [ -f "$output_file" ]; then
    content=()
    while IFS= read -r line || [ -n "$line" ]; do
        content+=("$line")
    done < "$output_file"
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

write_delay "Url [$r_Url] "
input=$(read_input)
new_r_Url="$input"

write_delay "ApiKey [${#r_ApiKey} chars] "
input=$(read_input secure)
write_mask ${#input}
new_r_ApiKey="$input"

write_delay "Endpoint [$r_Endpoint] "
input=$(read_input)
new_r_Endpoint="$input"

write_delay ""
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~          Sonarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay "??? Lookup the API key for Sonarr in: Settings ... General ... Security"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""

write_delay "Url [$s_Url] "
input=$(read_input)
new_s_Url="$input"

write_delay "ApiKey [${#s_ApiKey} chars] "
input=$(read_input secure)
write_mask ${#input}
new_s_ApiKey="$input"

write_delay "Endpoint [$s_Endpoint] "
input=$(read_input)
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

write_delay "Url [$QUrl] "
input=$(read_input)
new_QUrl="$input"

write_delay "ApiKey [${#QApiKey} chars] "
input=$(read_input secure)
write_mask ${#input}
new_QApiKey="$input"

if [ "$new_QApiKey" = "-" ]; then
    write_delay "You have chosen to use username/password authentication."
    write_delay "Username [$QUsername] "
    input=$(read_input)
    new_QUsername="$input"
    write_delay "Password [${#QPassword} chars] "
    input=$(read_input secure)
    write_mask ${#input}
    new_QPassword="$input"
else
    new_QUsername=""
    new_QPassword=""
fi

write_delay "Endpoint [$QEndpoint] "
input=$(read_input)
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
write_setting_value "Radarr" "Url" "$new_r_Url" "$r_Url"
write_setting_value "Radarr" "ApiKey" "$new_r_ApiKey" "$r_ApiKey"
write_setting_value "Radarr" "Endpoint" "$new_r_Endpoint" "$r_Endpoint"

write_setting_value "Sonarr" "Url" "$new_s_Url" "$s_Url"
write_setting_value "Sonarr" "ApiKey" "$new_s_ApiKey" "$s_ApiKey"
write_setting_value "Sonarr" "Endpoint" "$new_s_Endpoint" "$s_Endpoint"

write_setting_value "qBittorrent" "QUrl" "$new_QUrl" "$QUrl"
write_setting_value "qBittorrent" "QApiKey" "$new_QApiKey" "$QApiKey"
write_setting_value "qBittorrent" "QUsername" "$new_QUsername" "$QUsername"
write_setting_value "qBittorrent" "QPassword" "$new_QPassword" "$QPassword"
write_setting_value "qBittorrent" "QEndpoint" "$new_QEndpoint" "$QEndpoint"

write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
if [ -f "$output_file" ]; then
    datetime=$(date +%Y%m%d_%H%M%S)
    output_file_bak="$output_file-$datetime.bak"
    mv "$output_file" "$output_file_bak"
    write_delay "~~~ Moving old settings file: $output_file_bak"
fi
write_delay "~~~ Writing settings to file: $output_file"
printf "%s\n" "${content[@]}" > "$output_file"
write_delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
write_delay ""
write_delay "Done!"
write_delay "Reloading configuration..." 1000

exit 0