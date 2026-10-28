$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath('C:\Users\Administrator\Downloads\proj\[화웨이_데이타]')
$prefix = $root.TrimEnd('\') + '\'
$groups = [ordered]@{
 '01_제안서_입찰_RFP' = @(
  @('(정류기 배터리)제안서 평가 제출 자료','정류기_배터리_제안평가_제출자료'),
  @('(250415)대형리튬인산철축전지 RFP 제안서 평가 제출 자료 List(정류기용).xlsx',''),
  @('신규 정류기(3KW_6KW) 제안서_1차 초안.pptx',''),
  @('신규 정류기(3KW_6KW) 제안서_3-1차 초안.pptx',''),
  @('실내 기술 자료 및 RFP draft version','실내설비_UPS_정류기_RFP_기술자료'),
  @('실내 기술 자료 및 RFP draft version.zip',''),
  @('요구규격서_48V 정류기용 대용량_리튬인산철축전지_팬택씨앤아이엔지니어링.docx','')
 )
 '02_제품자료_정류기_축전지' = @(
  @('6KW 화웨이 자료','화웨이_3KW_6KW_정류기'),
  @('LGU 전원공급장치 관련 자료','LGU_전원공급장치'),
  @('[첨부1] Blade Battery Datasheet','블레이드_배터리_제품사양_통신규격'),
  @('(2.1.2) Huawei CloudLi ESM-48100C1 Datasheet (SKT)_1204.pptx',''),
  @('소형축전지.txt','소형축전지_검토메모.txt'),
  @('축전지 원격차단.pdf',''),
  @('축전지 원격차단.pptx','')
 )
 '04_감시시스템_통신_웹UI' = @(
  @('250901_웹UI','20250901_웹UI_감시교육_사진영상'),
  @('[SMU02C]','SMU02C_펌웨어_SNMP_MIB'),
  @('[행복나래_감시기능 전달]','행복나래_감시기능_연동자료'),
  @('screenshot','LCD_메뉴_화면캡처'),
  @('화면캡처','웹_앱_SNMP_화면캡처'),
  @('(냉난방_RMS) NetCol8000-A In-room Air Cooled Smart Cooling Product Modbus  Protocol (V100R021C10).pdf',''),
  @('수정사항.txt','감시기능_수정사항.txt'),
  @('트랩내용.txt','SNMP_트랩_알람목록.txt')
 )
 '05_시험결과_현장출장' = @(
  @('IPDC','IPDC_현장사진_20250704'),
  @('[국내출장]','국내출장_현장별자료'),
  @('[대형정류기&축전지 연동시험]','대형정류기_축전지_연동시험'),
  @('ESM-48100C10_환경시험 결과_260422.pdf',''),
  @('ESM-48100C10_환경시험 결과_260422.pptx',''),
  @('SMU신규펌웨어_축전지테스트.pptx',''),
  @('정류기_확인시험(2025_09_18).pptx',''),
  @('축전지테스트.pptx',''),
  @('환경시험 결과.pptx','')
 )
 '06_서버접속_보안점검' = @(
  @('2차 보안점검(250227)','20250227_2차_보안점검'),
  @('NetEcho_보안진단','NetEcho_보안진단'),
  @('분당에서 보라매 서버로 접속하는 주소 정보.docx',''),
  @('싱가포르_netecho서버.txt','')
 )
 '99_과거자료' = @(@('OLD_SKTS_정류기','SK텔레시스_정류기_과거자료'))
}
function Assert-InRoot([string]$path) {
 $full = [IO.Path]::GetFullPath($path)
 if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Outside target directory: $full" }
}
$plan = [Collections.Generic.List[object]]::new()
foreach ($category in $groups.Keys) {
 foreach ($entry in $groups[$category]) {
  $name = $entry[0]; $newName = $entry[1]
  if (-not $newName) { $newName = $name }
  $plan.Add([pscustomobject]@{Old=$name; New=($category + '\' + $newName)})
 }
}
$plan.Add([pscustomobject]@{Old='[메뉴얼]'; New='03_매뉴얼_교육자료'})
$top = @(Get-ChildItem -LiteralPath $root -Force)
if ($top.Count -ne $plan.Count) { throw "Unexpected top-level count: $($top.Count); planned $($plan.Count)" }
foreach ($item in $top) { if ($item.Name -notin $plan.Old) { throw "Unclassified item: $($item.Name)" } }
foreach ($item in $plan) {
 $src = Join-Path $root $item.Old; $dst = Join-Path $root $item.New
 Assert-InRoot $src; Assert-InRoot $dst
 if (-not (Test-Path -LiteralPath $src)) { throw "Missing source: $src" }
 if (Test-Path -LiteralPath $dst) { throw "Destination exists: $dst" }
}
$before = @(Get-ChildItem -LiteralPath $root -Recurse -Force)
if (@($before | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Reparse points found; review required.' }
$expected = foreach ($item in $before) {
 $rel = $item.FullName.Substring($prefix.Length)
 $first = $rel.Split('\')[0]
 $mapping = $plan | Where-Object Old -EQ $first
 if (-not $mapping) { throw "No mapping: $rel" }
 [pscustomobject]@{Old=$rel; New=($mapping.New + $rel.Substring($first.Length)); IsDirectory=$item.PSIsContainer; Length= $(if ($item.PSIsContainer) {0} else {$item.Length}); LastWriteUtc=$item.LastWriteTimeUtc.Ticks}
}
$audit = Join-Path $root '99_과거자료\정리이력'
Assert-InRoot $audit
New-Item -ItemType Directory -Path $audit -Force | Out-Null
$expected | Export-Csv -LiteralPath (Join-Path $audit '이동전후_전체목록.csv') -NoTypeInformation -Encoding UTF8
$plan | Export-Csv -LiteralPath (Join-Path $audit '폴더_이동계획.csv') -NoTypeInformation -Encoding UTF8
foreach ($item in $plan) {
 $src = Join-Path $root $item.Old; $dst = Join-Path $root $item.New
 Assert-InRoot $src; Assert-InRoot $dst
 $parent = Split-Path -Parent $dst
 if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
 Move-Item -LiteralPath $src -Destination $dst
 Add-Content -LiteralPath (Join-Path $audit '이동완료.log') -Value ($item.Old + ' -> ' + $item.New) -Encoding UTF8
}
$files = 0; $bytes = [long]0
foreach ($entry in $expected) {
 $dst = Join-Path $root $entry.New
 $actual = Get-Item -LiteralPath $dst -Force
 if ($actual.PSIsContainer -ne $entry.IsDirectory) { throw "Type mismatch: $dst" }
 if (-not $entry.IsDirectory) {
  if ($actual.Length -ne $entry.Length -or $actual.LastWriteTimeUtc.Ticks -ne $entry.LastWriteUtc) { throw "File mismatch: $dst" }
  $files++; $bytes += $actual.Length
 }
}
$guide = @'
화웨이 자료 폴더 안내

01_제안서_입찰_RFP : 제안서 초안, 입찰·평가 제출자료, 요구규격서, UPS·정류기 RFP
02_제품자료_정류기_축전지 : 제품 사양, 3KW·6KW 정류기, LGU 전원장치, 블레이드 배터리, 원격차단
03_매뉴얼_교육자료 : 기존 [메뉴얼] 자료 전체. 설치·운용·교육·기술 매뉴얼
04_감시시스템_통신_웹UI : SMU02C 펌웨어, SNMP·MIB·Modbus, 행복나래 연동, 웹UI·LCD·앱 화면
05_시험결과_현장출장 : 환경시험·축전지시험·연동시험, 국내출장, IPDC 현장사진
06_서버접속_보안점검 : 서버 접속정보, NetEcho 보안진단, 취약점 점검·조치자료
99_과거자료 : SK텔레시스 과거 정류기 자료 및 이번 정리의 경로 기록

관련 자료 묶음은 내부 구성을 유지했습니다. 중복으로 보이는 파일이나 이전 버전도 삭제하지 않았습니다.
실내 기술 자료 ZIP과 원본 폴더는 함께 보관했습니다.
원래 경로와 새 경로는 99_과거자료\정리이력\이동전후_전체목록.csv에서 확인할 수 있습니다.
'@
Set-Content -LiteralPath (Join-Path $root '00_폴더안내.txt') -Value $guide -Encoding UTF8
$summary = "Verified: $files files, $bytes bytes; $($plan.Count) top-level items organized."
Set-Content -LiteralPath (Join-Path $audit '검증결과.txt') -Value $summary -Encoding UTF8
Write-Output $summary
Get-ChildItem -LiteralPath $root -Force | Select-Object Name
