<#
  Undo-Tidy.ps1 -- moves every file back to where it was, using moves-log.csv
  Usage:  .\Undo-Tidy.ps1 -Log "C:\Users\<you>\Desktop\PC-Tidy-Report-XXXX\moves-log.csv"
#>
param([Parameter(Mandatory)][string]$Log)

Import-Csv $Log | ForEach-Object {
    if ((Test-Path -LiteralPath $_.To) -and -not (Test-Path -LiteralPath $_.From)) {
        Move-Item -LiteralPath $_.To -Destination $_.From
        Write-Host "Restored: $($_.From)"
    }
}
