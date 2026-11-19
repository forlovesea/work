param(
    [Parameter(Mandatory=$true)][string]$InputDocx,
    [Parameter(Mandatory=$true)][string]$OutputPdf
)
# Optional visual QA helper. Requires an installed, activated Microsoft Word.
# Opens only the named test document read-only, disables macros, exports and closes.
$ErrorActionPreference = 'Stop'
$inputAbsolute = (Resolve-Path -LiteralPath $InputDocx).Path
$outputAbsolute = [System.IO.Path]::GetFullPath($OutputPdf)
$wordApp = $null
$testDocument = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $testDocument = $wordApp.Documents.Open($inputAbsolute, $false, $true)
    $testDocument.ExportAsFixedFormat($outputAbsolute, 17)
    Write-Output 'PASS: Microsoft Word rendered the test DOCX to PDF'
}
finally {
    $saveChanges = 0
    try {
        if ($null -ne $testDocument) {
            $testDocument.Close([ref]$saveChanges)
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($testDocument)
        }
    }
    finally {
        if ($null -ne $wordApp) {
            $wordApp.Quit([ref]$saveChanges)
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)
        }
    }
}
