param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$archifyCli = "C:\Users\AKMALSAFARIPELLU\.gemini\config\skills\archify\bin\archify.mjs"
if (-not (Test-Path $archifyCli)) {
    Write-Error "Archify CLI not found at $archifyCli"
    exit 1
}

node $archifyCli @Arguments
exit $LASTEXITCODE
