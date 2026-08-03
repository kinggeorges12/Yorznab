# console.ps1
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

safe_eval() {
    local input="$1"
    
    if [ -n "$input" ]; then
        # Escape backslashes and double quotes (the essential ones)
        local escaped="${input//\\/\\\\}"
        escaped="${escaped//\"/\\\"}"
        
        # Optional but recommended: escape dollar signs to prevent variable expansion
        escaped="${escaped//\$/\\$}"
        
        # Optional but recommended: escape backticks to prevent command substitution
        escaped="${escaped//\`/\\\`}"
        
        eval "$escaped"
    fi
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
write_delay "╽       ...a Torznab Indexer that's all YORZ                                   ╽" 1000
write_delay "╿                                                                              ╿"
write_delay "╰╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╯"
write_delay "This is your command console!"

write_delay "Enter any command to execute on the Yorznab server."
while true; do
    write_delay "> " "" "true"
    input=$(read_input)
    if [ -n "$input" ]; then
        safe_eval "$input"
    fi
done
