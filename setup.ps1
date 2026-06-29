# setup.ps1

$ErrorActionPreference = "Stop"
function Read-KeyWithTimeout {
    param(
        [bool]$AlreadyGotKey,
        [int]$TimeoutMs = 1000
    )

    if ($AlreadyGotKey) {
        return [PSCustomObject]@{
            Key           = $null
            AlreadyGotKey = $true
        }
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        if ([Console]::KeyAvailable) {
            return [PSCustomObject]@{
                Key           = [Console]::ReadKey($true).KeyChar
                AlreadyGotKey = $true   # Stop future reads
            }
        }

        Start-Sleep -Milliseconds 50
    }

    # Timed out, so allow the next read
    return [PSCustomObject]@{
        Key           = $null
        AlreadyGotKey = $false
    }
}
$gotKey = $false
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗"
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "║                                                                              ║"
Write-Host "║       ██╗   ██╗ ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██████╗ ██╗        ║"
Write-Host "║       ╚██╗ ██╔╝██╔═══██╗██╔══██╗╚══███╔╝████╗  ██║██╔══██╗██╔══██╗██║        ║"
Write-Host "║        ╚████╔╝ ██║   ██║██████╔╝  ███╔╝ ██╔██╗ ██║███████║██████╔╝██║        ║"
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "║         ╚██╔╝  ██║   ██║██╔══██╗ ███╔╝  ██║╚██╗██║██╔══██║██╔══██╗╚═╝        ║"
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "║          ██║   ╚██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║██████╔╝██╗        ║"
Write-Host "║          ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═════╝ ╚═╝        ║"
Write-Host "║══════════════════════════════════════════════════════════════════════════════║"
Write-Host "║                                                                              ║"
Write-Host "║                                         ...a Torznab Indexer that's all YORZ ║"
$r = Read-KeyWithTimeout $gotKey -TimeoutMs 2000
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "║                                                                              ║"
Write-Host "║              Please fill-in the fields below to get started.                 ║"
Write-Host "║                                                                              ║"
Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝"
Write-Host ""
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey

# Define output file
$output_file = "config/settings.yaml"

$current_dir = Get-Location
$script_dir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($current_dir.Path -ne $script_dir) {
    Write-Host "Install: $script_dir"
    Write-Host "Current: $current_dir"
    $reply = Read-Host "Are you in the correct directory? yes(Y)/[no(N)]/go(G) "
    Write-Host ""
    if ($reply -match "^[Gg]$") {
        Set-Location $script_dir
        Write-Host "Switching directory: $(Get-Location)"
    } elseif ($reply -notmatch "^[Yy]$") {
        Write-Host "Cancelling..."
        exit 1
    }
    Write-Host "Continuing..."
}

if (Test-Path $output_file) {
    Write-Host "It looks like the settings file was already created."
    $reply = Read-Host "Do you want to (O)verwrite some values or (K)eep it the way it is? "
    Write-Host ""
    if ($reply -eq "") {
        Write-Host "Alright, hang on!"
    } elseif ($reply -notmatch "^[Oo]$") {
        Write-Host "Keeping it the way it is... Bye!"
        exit 1
    }
    Write-Host "Continuing..."
}

function Read-Password {
    $password = ""
    $char = $null

    # Store original console settings
    $original = [Console]::TreatControlCAsInput
    [Console]::TreatControlCAsInput = $true
    
    while ($true) {
        $key = [Console]::ReadKey($true)
        
        # Enter key
        if ($key.Key -eq "Enter") {
            break
        }
        # Backspace
        elseif ($key.Key -eq "Backspace") {
            if ($password.Length -gt 0) {
                $password = $password.Substring(0, $password.Length - 1)
                Write-Host "`b `b" -NoNewline
            }
        }
        # All other keys
        else {
            $char = $key.KeyChar
            $password += $char
            Write-Host "*" -NoNewline
        }
    }
    
    [Console]::TreatControlCAsInput = $original
    Write-Host ""
    return $password
}

# Read existing settings from YAML file
function Get-SettingValue {
    param($section, $field)
    $content = Get-Content $output_file -ErrorAction SilentlyContinue
    if ($content) {
        $inSection = $false
        foreach ($line in $content) {
            if ($line -match "^${section}:") {
                $inSection = $true
                continue
            }
            if ($inSection -and $line -match "^  ${field}:\s+(.+)$") {
                return $matches[1]
            }
            if ($inSection -and $line -match "^[^ ]" -and $line -notmatch " ") {
                $inSection = $false
            }
        }
    }
    return $null
}

$r_Url = Get-SettingValue "Radarr" "Url"
if (-not $r_Url) { $r_Url = "http://localhost:7878" }
$r_ApiKey = Get-SettingValue "Radarr" "ApiKey"
$r_Endpoint = Get-SettingValue "Radarr" "Endpoint"
if (-not $r_Endpoint) { $r_Endpoint = "/api/v3/movie" }

$s_Url = Get-SettingValue "Sonarr" "Url"
if (-not $s_Url) { $s_Url = "http://localhost:8989" }
$s_ApiKey = Get-SettingValue "Sonarr" "ApiKey"
$s_Endpoint = Get-SettingValue "Sonarr" "Endpoint"
if (-not $s_Endpoint) { $s_Endpoint = "/api/v3/series" }

$QUrl = Get-SettingValue "qBittorrent" "QUrl"
if (-not $QUrl) { $QUrl = "http://localhost:8080" }
$QApiKey = Get-SettingValue "qBittorrent" "QApiKey"
$QUsername = Get-SettingValue "qBittorrent" "QUsername"
$QPassword = Get-SettingValue "qBittorrent" "QPassword"
$QEndpoint = Get-SettingValue "qBittorrent" "QEndpoint"
if (-not $QEndpoint) { $QEndpoint = "/api/v2" }

# Prompt user for inputs
Write-Host ""
Write-Host ""
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host ""
Write-Host "To keep current settings, press enter."
Write-Host "To delete a setting, type '-' and press enter."
Write-Host "Default settings for Endpoints are usually fine for a basic setup."
Write-Host ""

$gotKey = $false
$r = Read-KeyWithTimeout $gotKey -TimeoutMs 2000
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~          Radarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host ""
Write-Host ">>> Lookup the API key for Radarr in: Settings > General > Security"
Write-Host ""
$new_r_Url = Read-Host "Url (current: $r_Url)"
Write-Host -NoNewline "ApiKey (current: $($r_ApiKey.Length) chars): "
$new_r_ApiKey = Read-Password
$new_r_Endpoint = Read-Host "Endpoint (current: $r_Endpoint)"

Write-Host ""
$gotKey = $false
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~          Sonarr            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host ""
Write-Host ">>> Lookup the API key for Sonarr in: Settings > General > Security"
Write-Host ""
$new_s_Url = Read-Host "Url (current: $s_Url)"
Write-Host -NoNewline "ApiKey (current: $($s_ApiKey.Length) chars): "
$new_s_ApiKey = Read-Password
$new_s_Endpoint = Read-Host "Endpoint (current: $s_Endpoint)"

Write-Host ""
$gotKey = $false
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~        qBittorrent         ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~                            ~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Host ""
Write-Host ">>> Login settings for qBittorrent are in: [Menu] Tools > Options > WebUI"
Write-Host "*** Newer versions of qBittorrent allow for API authentication!"
Write-Host "*** Enter a dash '-' for the QApiKey if using username/password authentication."
Write-Host ""
Write-Host "Newer versions of qBittorrent allow an API key."
Write-Host "If your version does not support it, type a dash '-' and press enter."
Write-Host "You must supply a username and password."
Write-Host ""
$new_QUrl = Read-Host "Url (current: $QUrl)"
Write-Host -NoNewline "ApiKey (current: $($QApiKey.Length) chars): "
$new_QApiKey = Read-Password
$new_QUsername = Read-Host "Username (current: $QUsername)"
Write-Host -NoNewline "Password (current: $($QPassword.Length) chars): "
$new_QPassword = Read-Password
$new_QEndpoint = Read-Host "Endpoint (current: $QEndpoint)"
Write-Host ""

function Check-ForDash {
    param($field_name, $new_value, $default_value)
    
    if (-not $new_value -or $new_value -eq "") {
        return "  ${field_name}: $default_value"
    } elseif ($new_value -ne "-") {
        return "  ${field_name}: $new_value"
    }
    return $null
}

# Write inputs to file with a timestamp
Clear-Content $output_file -ErrorAction SilentlyContinue

@"
### Auto-generated by setup.ps1 ###

Radarr:
$(Check-ForDash "Url" $new_r_Url $r_Url)
$(Check-ForDash "ApiKey" $new_r_ApiKey $r_ApiKey)
$(Check-ForDash "Endpoint" $new_r_Endpoint $r_Endpoint)
Sonarr:
$(Check-ForDash "Url" $new_s_Url $s_Url)
$(Check-ForDash "ApiKey" $new_s_ApiKey $s_ApiKey)
$(Check-ForDash "Endpoint" $new_s_Endpoint $s_Endpoint)
qBittorrent:
$(Check-ForDash "QUrl" $new_QUrl $QUrl)
$(Check-ForDash "QApiKey" $new_QApiKey $QApiKey)
$(Check-ForDash "QUsername" $new_QUsername $QUsername)
$(Check-ForDash "QPassword" $new_QPassword $QPassword)
$(Check-ForDash "QEndpoint" $new_QEndpoint $QEndpoint)
"@ | Out-File $output_file -Encoding utf8

Write-Host ""
Write-Host "Settings written to: $output_file"
Write-Host "Until next time, enjoy YOR very own Yorznab!"
$gotKey = $false
$r = Read-KeyWithTimeout $gotKey
$key, $gotKey = $r.Key, $r.AlreadyGotKey

