$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile('C:\projects\sonata-nvda-64\tools\validateSonataNvdaRuntime.ps1', [ref]$null, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
    $errors | ForEach-Object { $_.ToString() }
    exit 1
} else {
    Write-Output 'PARSE_OK'
    exit 0
}
