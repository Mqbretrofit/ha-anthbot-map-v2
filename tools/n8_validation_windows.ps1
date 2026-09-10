param(
    [Parameter(Mandatory=$false)]
    [string]$Before,

    [Parameter(Mandatory=$false)]
    [string]$After,

    [Parameter(Mandatory=$false)]
    [string]$BeforeMap,

    [Parameter(Mandatory=$false)]
    [string]$AfterMap,

    [Parameter(Mandatory=$false)]
    [string]$Output = "n8_validation_diff.json",

    [Parameter(Mandatory=$false)]
    [string]$Summary = "n8_validation_summary.txt"
)

$ErrorActionPreference = "Stop"

function Select-FilePath([string]$Prompt) {
    $value = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $null
    }
    return $value.Trim('"')
}

if (-not $Before) {
    $Before = Select-FilePath "Huzd ide vagy add meg a BEFORE diagnostics JSON fajlt"
}
if (-not $After) {
    $After = Select-FilePath "Huzd ide vagy add meg az AFTER diagnostics JSON fajlt"
}

if (-not $Before -or -not (Test-Path -LiteralPath $Before)) {
    throw "A BEFORE diagnostics JSON nem talalhato: $Before"
}
if (-not $After -or -not (Test-Path -LiteralPath $After)) {
    throw "Az AFTER diagnostics JSON nem talalhato: $After"
}

if (($BeforeMap -and -not $AfterMap) -or ($AfterMap -and -not $BeforeMap)) {
    throw "A map-manager osszehasonlitashoz a BeforeMap es AfterMap fajlt egyutt kell megadni."
}
if ($BeforeMap -and -not (Test-Path -LiteralPath $BeforeMap)) {
    throw "A BEFORE map_manager archive nem talalhato: $BeforeMap"
}
if ($AfterMap -and -not (Test-Path -LiteralPath $AfterMap)) {
    throw "Az AFTER map_manager archive nem talalhato: $AfterMap"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonTool = Join-Path $ScriptDir "n8_validation_bundle.py"
$InterpretTool = Join-Path $ScriptDir "n8_validation_interpret.py"
if (-not (Test-Path -LiteralPath $PythonTool)) {
    throw "Hianyzik: $PythonTool"
}
if (-not (Test-Path -LiteralPath $InterpretTool)) {
    throw "Hianyzik: $InterpretTool"
}

$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    $PythonExe = "py"
    $PythonPrefix = @("-3")
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) {
        throw "Python 3 nem talalhato. Telepitsd a Python 3-at, majd futtasd ujra ezt a scriptet."
    }
    $PythonExe = "python"
    $PythonPrefix = @()
}

$argsList = @()
$argsList += $PythonPrefix
$argsList += $PythonTool
$argsList += $Before
$argsList += $After
if ($BeforeMap -and $AfterMap) {
    $argsList += "--before-map"
    $argsList += $BeforeMap
    $argsList += "--after-map"
    $argsList += $AfterMap
}
$argsList += "--json"

Write-Host ""
Write-Host "N8 validation osszehasonlitas indul..."
$result = & $PythonExe @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Az N8 validation comparer hibaval allt le (exit code: $LASTEXITCODE)."
}

$result | Set-Content -LiteralPath $Output -Encoding UTF8

$interpretArgs = @()
$interpretArgs += $PythonPrefix
$interpretArgs += $InterpretTool
$interpretArgs += $Output
$summaryText = & $PythonExe @interpretArgs
if ($LASTEXITCODE -ne 0) {
    throw "Az N8 validation interpreter hibaval allt le (exit code: $LASTEXITCODE)."
}
$summaryText | Set-Content -LiteralPath $Summary -Encoding UTF8

Write-Host ""
Write-Host "KESZ:"
Write-Host "  $Output"
Write-Host "  $Summary"
Write-Host ""
Write-Host "Mindket fajlt kuldd vissza elemzesre."
Write-Host ""
$summaryText
