# FleetWise Smartphone Connectivity Doctor (PowerShell Entrypoint)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$scriptDir\diagnose_phone.py"

