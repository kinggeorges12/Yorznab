# setup.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

function Write-Delay {
    param([string]$message,
          [int]$delay = 10,
          [switch]$NoNewline)
    if($NoNewline) {
        Write-Host $message -NoNewline
    } else {
        Write-Host $message
    }
    Start-Sleep -Milliseconds $delay
}

function Reader-Prompt {
    param([string]$message = "",
          [switch]$AsSecureString)
    Write-Delay $message
    if ($AsSecureString) {
        $input = Read-Host -AsSecureString
        $input = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($input))
    } else {
        $input = Read-Host
    }
    Write-Host ""
    $input
}

Write-Delay ""
Write-Delay "╭╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╮"
Write-Delay "╽                                                                              ╽"
Write-Delay "╿       ██╮   ██╮ ██████╮ ██████╮ ███████╮███╮   ██╮ █████╮ ██████╮ ██╮        ╿"
Write-Delay "╽       ╰██╮ ██╭╯██╭╼╾╼██╮██╭╼╾██╮╰╼╾███╭╯████╮  ██╽██╭╼╾██╮██╭╼╾██╮██╽        ╽" -Delay 100
Write-Delay "╿        ╰████╭╯ ██╽   ██╽██████╭╯  ███╭╯ ██╭██╮ ██╿███████╿██████╭╯██╿        ╿"
Write-Delay "╽         ╰██╭╯  ██╿   ██╿██╭╼╾██╮ ███╭╯  ██╽╰██╮██╽██╭╼╾██╽██╭╼╾██╮╰╼╯        ╽"
Write-Delay "╿          ██╿   ╰██████╭╯██╿  ██╿███████╮██╿ ╰████╿██╿  ██╿██████╭╯██╮        ╿"
Write-Delay "╽          ╰╼╯    ╰╼╾╼╾╼╯ ╰╼╯  ╰╼╯╰╼╾╼╾╼╾╯╰╼╯  ╰╼╾╼╯╰╼╯  ╰╼╯╰╼╾╼╾╼╯ ╰╼╯        ╽"
Write-Delay "╟╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╢" -Delay 100
Write-Delay "╿                                                                              ╿"
Write-Delay "╽       ...a Torznab Indexer that's all YORZ                                         ╽" -Delay 2000
Write-Delay "╿                                                                              ╿"
Write-Delay "╽              Please fill-in the fields below to get started.                 ╽"
Write-Delay "╿                                                                              ╿"
Write-Delay "╰╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╯"
Write-Delay -Delay 1000 ""

$current_dir = Get-Location
$script_dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Delay "Current directory: $current_dir"
if ($current_dir.Path -ne $script_dir) {
    Write-Delay "Script directory: $script_dir"
    $input = Reader-Prompt "Are you in the correct directory? yes(Y)/[no(N)]/go(G) "
    if ($input -match "^[Gg]$") {
        Set-Location $script_dir
        Write-Delay "Switching directory: $(Get-Location)"
    } elseif ($input -notmatch "^[Yy]$") {
        Write-Delay "Cancelling..."
        exit 1
    }
    Write-Delay "Continuing..."
}

# Read existing settings from YAML file
function Get-SettingValue {
    param([string[]]$content,
          [string]$section,
          [string]$field,
          [string]$default_value = "")
    if ($content) {
        $inSection = $false
        foreach ($line in $content) {
            if ($line -match "^${section}:") {
                $inSection = $true
                continue
            }
            if ($inSection -and $line -match "^  ${field}:(.+)$") {
                $matched = $matches[1]
                break
            }
            if ($inSection -and $line -match "^[^ ]") {
                $inSection = $false
            }
        }
    }
    if($matched) {
        return $matched.Trim()
    }
    return $default_value
}

function Check-ForDefaults {
    param($field_name, $new_value, $default_value, $mask = $false)

    if (-not $new_value -or $new_value -eq "" -or $new_value -eq "=") {
        $default_value = if ($mask -and $default_value) { '*' * $default_value.Length } else { $default_value }
        return "  ${field_name}: $default_value"
    } elseif ($new_value -ne "-") {
        $new_value = if ($mask -and $new_value) { '*' * $new_value.Length } else { $new_value }
        return "  ${field_name}: $new_value"
    }
    return $null
}

# Read existing settings from YAML file
function Write-SettingValue {
    param([string[]]$content,
          [string]$section,
          [string]$field,
          [string]$new_value,
          [string]$default_value)
    $new_value = Check-ForDefaults $field $new_value $default_value
    $newLines = @()
    $inSection = $false
    $fieldFound = $false
    foreach ($line in $content) {
        if ($fieldFound) {
        } elseif ($line -match "^${section}:") {
            $inSection = $true
        } elseif ($inSection) {
            if ($line -match "^  ${field}:") {
                $fieldFound = $true
                $newLines += $new_value
                continue
            } elseif ($line -match "^[^ ]" -and $line -notmatch "^${section}:") {
                if (-not $fieldFound) {
                    $newLines += $new_value
                    $fieldFound = $true
                }
                $inSection = $false
            } 
        }
        $newLines += $line
    }
    if (-not $fieldFound) {
        if (-not $inSection) {
            $newLines += "${section}: ${new_value}"
        }
        $newLines += $new_value
    }
    return $newLines
}

# Define output file
$output_file = "config/settings.yaml"
# Read current settings
$content = Get-Content $output_file -ErrorAction SilentlyContinue

$r_Url = Get-SettingValue $content "Radarr" "Url" "http://localhost:7878"
$r_ApiKey = Get-SettingValue $content "Radarr" "ApiKey"
$r_Endpoint = Get-SettingValue $content "Radarr" "Endpoint" "/api/v3/movie"

$s_Url = Get-SettingValue $content "Sonarr" "Url" "http://localhost:8989"
$s_ApiKey = Get-SettingValue $content "Sonarr" "ApiKey"
$s_Endpoint = Get-SettingValue $content "Sonarr" "Endpoint" "/api/v3/series"

$QUrl = Get-SettingValue $content "qBittorrent" "QUrl" "http://localhost:8080"
$QApiKey = Get-SettingValue $content "qBittorrent" "QApiKey"
$QUsername = Get-SettingValue $content "qBittorrent" "QUsername"
$QPassword = Get-SettingValue $content "qBittorrent" "QPassword"
$QEndpoint = Get-SettingValue $content "qBittorrent" "QEndpoint" "/api/v2"

# Prompt user for inputs
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay ""
Write-Delay "To keep current settings, type '=' or just press enter."
Write-Delay "To delete a setting, type '-' and press enter."
Write-Delay "Default settings for Endpoints are usually fine for a basic setup."
Write-Delay -Delay 1000 ""

Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~          Radarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "??? Lookup the API key for Radarr in: Settings ... General ... Security"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay ""

$input = Reader-Prompt "Url [$r_Url]"
$new_r_Url = $input
$input = Reader-Prompt "ApiKey [$($r_ApiKey.Length) chars]" -AsSecureString
$new_r_ApiKey = $input
$input = Reader-Prompt "Endpoint [$r_Endpoint]"
$new_r_Endpoint = $input

Write-Delay ""
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~          Sonarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "??? Lookup the API key for Sonarr in: Settings ... General ... Security"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay ""

$input = Reader-Prompt "Url [$s_Url]"
$new_s_Url = $input
$input = Reader-Prompt "ApiKey [$($s_ApiKey.Length) chars]" -AsSecureString
$new_s_ApiKey = $input
$input = Reader-Prompt "Endpoint [$s_Endpoint]"
$new_s_Endpoint = $input

Write-Delay ""
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~        qBittorrent         ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "??? Login settings for qBittorrent are in: [Menu] Tools ... Options ... WebUI"
Write-Delay "*** Newer versions of qBittorrent allow for API authentication!"
Write-Delay "*** Enter a dash '-' for the QApiKey if using username/password authentication."
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay "%%% Newer versions of qBittorrent allow an API key."
Write-Delay "%%% If your version does not support it, type a dash '-' and press enter."
Write-Delay "%%% You must supply a username and password."
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay ""

$input = Reader-Prompt "Url [$QUrl]"
$new_QUrl = $input
$input = Reader-Prompt "ApiKey [$($QApiKey.Length) chars]" -AsSecureString
$new_QApiKey = $input
if ($new_QApiKey -eq "-") {
    Write-Delay "You have chosen to use username/password authentication."
    $input = Reader-Prompt "Username [$QUsername]"
    $new_QUsername = $input
    $input = Reader-Prompt "Password [$($QPassword.Length) chars]" -AsSecureString
    $new_QPassword = $input
} else {
    $new_QUsername = ''
    $new_QPassword = ''
}
$input = Reader-Prompt "Endpoint [$QEndpoint]"
$new_QEndpoint = $input

$print_settings = @"
### Auto-generated by setup.ps1 ###

Radarr:
$(Check-ForDefaults "Url" $new_r_Url $r_Url)
$(Check-ForDefaults "ApiKey" $new_r_ApiKey $r_ApiKey $true)
$(Check-ForDefaults "Endpoint" $new_r_Endpoint $r_Endpoint)
Sonarr:
$(Check-ForDefaults "Url" $new_s_Url $s_Url)
$(Check-ForDefaults "ApiKey" $new_s_ApiKey $s_ApiKey $true)
$(Check-ForDefaults "Endpoint" $new_s_Endpoint $s_Endpoint)
qBittorrent:
$(Check-ForDefaults "QUrl" $new_QUrl $QUrl)
$(Check-ForDefaults "QApiKey" $new_QApiKey $QApiKey $true)
$(Check-ForDefaults "QUsername" $new_QUsername $QUsername)
$(Check-ForDefaults "QPassword" $new_QPassword $QPassword $true)
$(Check-ForDefaults "QEndpoint" $new_QEndpoint $QEndpoint)
"@

Write-Delay ""
Write-Delay $print_settings
Write-Delay ""

$content = Write-SettingValue $content "Radarr" "Url" $new_r_Url $r_Url
$content = Write-SettingValue $content "Radarr" "ApiKey" $new_r_ApiKey $r_ApiKey
$content = Write-SettingValue $content "Radarr" "Endpoint" $new_r_Endpoint $r_Endpoint

$content = Write-SettingValue $content "Sonarr" "Url" $new_s_Url $s_Url
$content = Write-SettingValue $content "Sonarr" "ApiKey" $new_s_ApiKey $s_ApiKey
$content = Write-SettingValue $content "Sonarr" "Endpoint" $new_s_Endpoint $s_Endpoint

$content = Write-SettingValue $content "qBittorrent" "QUrl" $new_QUrl $QUrl
$content = Write-SettingValue $content "qBittorrent" "QApiKey" $new_QApiKey $QApiKey
$content = Write-SettingValue $content "qBittorrent" "QUsername" $new_QUsername $QUsername
$content = Write-SettingValue $content "qBittorrent" "QPassword" $new_QPassword $QPassword
$content = Write-SettingValue $content "qBittorrent" "QEndpoint" $new_QEndpoint $QEndpoint

Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
if (Test-Path $output_file) {
    $datetime = Get-Date -Format "yyyyMMdd_HHmmss"
    $output_file_bak = "$output_file-$datetime.bak"
    Move-Item $output_file $output_file_bak
    Write-Delay "~~~ Moving old settings file: $output_file_bak"
}
Write-Delay "~~~ Writing settings to file: $output_file"
[System.IO.File]::WriteAllLines($output_file, $content)
Write-Delay "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Delay ""
Write-Delay "Done!"
Write-Delay "Reloading configuration..." -Delay 1000

exit 0
