$scriptPath = 'C:\projects\sonata-nvda-64\tools\validateSonataNvdaRuntime.ps1'
$text = Get-Content -Raw $scriptPath
$errorsRef = [ref] @()
$tokensRef = [ref] @()
[System.Management.Automation.Language.Parser]::ParseInput($text, $tokensRef, $errorsRef) | Out-Null
if ($errorsRef.Value.Count -eq 0) {
    Write-Output 'PARSER_OK'
    exit 0
} else {
    Write-Output ('PARSER_ERRORS=' + $errorsRef.Value.Count)
    $errorsRef.Value | ForEach-Object { Write-Output $_.Message }
    exit 2
}
