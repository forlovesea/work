<?php
declare(strict_types=1);
require_once dirname(__DIR__) . '/lib/contact-privacy.php';
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
header('X-Content-Type-Options: nosniff');
$token = $_POST['token'] ?? $_GET['token'] ?? '';
$message = '유효하지 않거나 만료된 승인 링크입니다.';
$approval = false;
try {
    if (is_string($token) && preg_match('/^[a-f0-9]{64}$/', $token)) {
        $database = contactApprovalDatabase();
        $query = $database->prepare('SELECT id, purpose, record_ids, approved_at FROM contact_approvals WHERE token_hash = ? AND expires_at > ? AND consumed_at IS NULL');
        $query->execute([hash('sha256', $token), time()]);
        $approval = $query->fetch();
        if ($approval) {
            $label = $approval['purpose'] === 'view' ? '웹 조회 1회' : 'Excel 추출 1회';
            $count = count(json_decode($approval['record_ids'], true));
            $message = "pantech 사용자가 요청한 {$count}건의 담당자 이름·연락처 공개 ({$label})를 승인합니다.";
            if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['intent'] ?? '') !== 'inspect') {
                $update = $database->prepare('UPDATE contact_approvals SET approved_at = ? WHERE id = ? AND approved_at IS NULL AND consumed_at IS NULL AND expires_at > ?');
                $update->execute([time(), $approval['id'], time()]);
                $message = $update->rowCount() === 1 ? '인증 완료. 요청자는 원래 로그인한 화면에서 1회 공개를 사용할 수 있습니다.' : '이미 처리되었거나 만료된 요청입니다.';
                $approval = false;
            } elseif ($approval['approved_at'] !== null) {
                $message = '이미 인증 완료된 요청입니다.';
                $approval = false;
            }
        }
    }
} catch (Throwable $error) {
    http_response_code(503);
    $message = '승인 요청을 처리하지 못했습니다. 관리자에게 문의해 주세요.';
    $approval = false;
}
function approvalEscape(string $value): string { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
?>
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>담당자 개인정보 공개 승인</title><script src="assets/approval-link.js" defer></script></head>
<body><main><h1>담당자 개인정보 공개 승인</h1><p><?= approvalEscape($message) ?></p>
<form id="approvalInspect" method="post" action="approve-contacts.php" hidden><input type="hidden" name="intent" value="inspect"><input type="hidden" name="token" value=""></form>
<noscript>이메일 승인 링크를 확인하려면 JavaScript를 활성화해 주세요.</noscript>
<?php if ($approval): ?>
<p>요청 번호: <?= approvalEscape($approval['id']) ?></p>
<p>관리자 forlovesea@gmail.com에게 발송된 승인 링크입니다. 요청 내용을 확인한 경우에만 인증 완료를 클릭하세요. 요청 후 15분이 지나면 만료됩니다.</p>
<form method="post" action="approve-contacts.php"><input type="hidden" name="token" value="<?= approvalEscape($token) ?>"><button type="submit">인증 완료</button></form>
<?php endif; ?>
</main></body></html>
