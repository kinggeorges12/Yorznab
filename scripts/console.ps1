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


function Invoke-SafeExpression {
param(
    [string]$Command
)

    # Escape the command string for safe use with Invoke-Expression
    function Escape-ForInvokeExpression {
        param([string]$InputString)
        
        # Escape backticks first (double them)
        $escaped = $InputString -replace '`', '``'
        
        # Escape double quotes
        $escaped = $escaped -replace '"', '`"'
        
        # Escape variable prefix
        $escaped = $escaped -replace '\$', '`$'
        
        # Escape special characters
        $escaped = $escaped -replace '@', '`@'
        $escaped = $escaped -replace '%', '`%'
        $escaped = $escaped -replace '&', '`&'
        $escaped = $escaped -replace '\(', '`('
        $escaped = $escaped -replace '\)', '`)'
        $escaped = $escaped -replace '\{', '`{'
        $escaped = $escaped -replace '\}', '`}'
        $escaped = $escaped -replace '\[', '`['
        $escaped = $escaped -replace '\]', '`]'
        $escaped = $escaped -replace ';', '`;'
        $escaped = $escaped -replace '\|', '`|'
        $escaped = $escaped -replace '<', '`<'
        $escaped = $escaped -replace '>', '`>'
        $escaped = $escaped -replace '\?', '`?'
        $escaped = $escaped -replace '\*', '`*'
        
        return $escaped
    }

    # Escape the command
    $escapedCommand = Escape-ForInvokeExpression -InputString $Command

    # Execute with Invoke-Expression
    try {
        Invoke-Expression "$escapedCommand"
    }
    catch {
        Write-Error "$_"
    }
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
Write-Delay "╽       ...a Torznab Indexer that's all YORZ                                   ╽" -Delay 2000
Write-Delay "╿                                                                              ╿"
Write-Delay "╰╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╯"
Write-Delay ""
Write-Delay -Delay 1000 "This is your command console!"

$command = Read-Host "Enter any command to execute on the Yorznab server."
while ($true) {
    $command = Read-Host
    Invoke-SafeExpression -Command $command
}
