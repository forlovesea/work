$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $files = @((Join-Path $project 'app/src/main/assets/charge.docx'), (Join-Path $project 'app/src/main/assets/outage.docx'))
    $files += @(Get-ChildItem -LiteralPath (Join-Path $project 'qa/generated') -Filter '*.docx' | ForEach-Object FullName)
    foreach ($file in $files) {
        $doc = $null
        try {
            $doc = $word.Documents.Open($file, $false, $true, $false)
            $target = [IO.Path]::ChangeExtension($file, '.pdf')
            if ($file.Contains('assets')) { $target = Join-Path $project ('qa/reference-' + [IO.Path]::GetFileNameWithoutExtension($file) + '.pdf') }
            $doc.ExportAsFixedFormat($target, 17)
            Write-Output ('Rendered: ' + $target)
        } finally { if ($doc) { $doc.Close(0); [Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null } }
    }
} finally { $word.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null }
