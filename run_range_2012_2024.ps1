param(
  [string]$Start = "2012-01-01",
  [string]$End   = "2024-12-31"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (!(Test-Path ".\.venv")) { py -m venv .venv }
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
python .\forexfactory_pipeline.py run --config .\config.yaml --start $Start --end $End
Write-Host "Done. See outputs/"
