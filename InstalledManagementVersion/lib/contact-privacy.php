<?php
declare(strict_types=1);
require_once __DIR__ . '/approval-mail.php';

const CONTACT_APPROVER = 'forlovesea@gmail.com';

function contactsRestricted(): bool
{
    // Sessions created before role tracking must log in again for unrestricted access.
    return ($_SESSION['account_role'] ?? 'secondary') !== 'primary';
}

function maskContactName(string $name): string
{
    $chars = preg_split('//u', $name, -1, PREG_SPLIT_NO_EMPTY);
    if (!$chars) return '';
    if (count($chars) <= 2) $chars[count($chars) - 1] = '*';
    else for ($i = 1; $i < count($chars) - 1; $i++) $chars[$i] = '*';
    return implode('', $chars);
}

function maskContactPhone(string $phone): string
{
    if (preg_match('/^(\+82[- ]?)?(0?\d{1,3})([- ])(\d{3,4})([- ])(\d{4})$/', $phone, $parts)) {
        return $parts[1] . $parts[2] . $parts[3] . str_repeat('*', strlen($parts[4])) . $parts[5] . $parts[6];
    }
    $digits = preg_replace('/\D/', '', $phone);
    $length = strlen($digits);
    $start = $length >= 9 ? (substr($digits, 0, 2) === '02' ? 2 : 3) : 0;
    $end = $length >= 9 ? $length - 4 : $length;
    $index = 0;
    return preg_replace_callback('/\d/', static function ($match) use (&$index, $start, $end) {
        $position = $index++;
        return $position >= $start && $position < $end ? '*' : $match[0];
    }, $phone);
}

function maskContactPayload(array $payload): array
{
    foreach ($payload as $key => &$value) {
        if ($key === 'contacts' && is_array($value)) {
            foreach ($value as &$contact) {
                $contact['name'] = maskContactName((string) ($contact['name'] ?? ''));
                $contact['phone'] = maskContactPhone((string) ($contact['phone'] ?? ''));
            }
            unset($contact);
            $payload['contacts_masked'] = true;
        } elseif ($key === '담당자 정보') {
            $value = ['before' => '비공개', 'after' => '비공개'];
        } elseif (is_array($value)) {
            $value = maskContactPayload($value);
        }
    }
    unset($value);
    return $payload;
}

function resolveContactEdits($submitted, array $original, array &$errors): array
{
    if (!is_array($submitted) || count($submitted) > 20) {
        $errors[] = '담당자 정보는 최대 20명까지 입력해 주세요.';
        return [];
    }
    $result = [];
    foreach ($submitted as $contact) {
        if (!is_array($contact)) { $errors[] = '담당자 입력 형식을 확인해 주세요.'; continue; }
        $reference = $contact['original_contact'] ?? null;
        $old = null;
        if ($reference !== null) {
            if (!is_array($reference) || !is_int($reference['index'] ?? null) || !isset($original[$reference['index']])) {
                $errors[] = '담당자 정보가 변경되었습니다. 다시 조회한 후 수정해 주세요.';
                continue;
            }
            $old = $original[$reference['index']];
            if (($reference['name'] ?? null) !== maskContactName($old['name']) || ($reference['phone'] ?? null) !== maskContactPhone($old['phone'])) {
                $errors[] = '담당자 정보가 변경되었습니다. 다시 조회한 후 수정해 주세요.';
                continue;
            }
        }
        $resolved = [];
        foreach (['name', 'phone'] as $key) {
            $value = $contact[$key] ?? '';
            if (!is_string($value)) { $errors[] = '담당자 이름과 연락처를 문자로 입력해 주세요.'; continue; }
            $value = trim($value);
            if ($old !== null && $value === $reference[$key]) $resolved[$key] = $old[$key];
            elseif (strpos($value, '*') !== false) $errors[] = '수정할 이름 또는 연락처는 * 없이 전체 값을 입력해 주세요. 변경하지 않은 항목은 그대로 두세요.';
            else $resolved[$key] = $value;
        }
        $result[] = $resolved;
    }
    return $result;
}

function contactApprovalDatabase(): PDO
{
    $database = new PDO('sqlite:' . dirname(__DIR__) . '/data/installed-management.sqlite');
    $database->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $database->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $database->exec('PRAGMA busy_timeout = 5000');
    $database->exec('CREATE TABLE IF NOT EXISTS contact_approvals (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, purpose TEXT NOT NULL,
        record_ids TEXT NOT NULL, snapshot_hash TEXT NOT NULL, token_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        approved_at INTEGER, consumed_at INTEGER
    )');
    return $database;
}

function contactApprovalOwner(): string
{
    if (!isset($_SESSION['contact_approval_owner'])) $_SESSION['contact_approval_owner'] = bin2hex(random_bytes(32));
    return $_SESSION['contact_approval_owner'];
}

function contactApprovalRecords(PDO $database, array $ids): array
{
    $query = $database->prepare('SELECT * FROM records WHERE id IN (' . implode(',', array_fill(0, count($ids), '?')) . ') ORDER BY id');
    $query->execute($ids);
    return $query->fetchAll();
}

function contactSnapshotHash(array $records): string
{
    return hash('sha256', json_encode(array_map(static fn($record) => [$record['id'], $record['contacts_json']], $records), JSON_THROW_ON_ERROR));
}

function handleContactApproval(array $input): void
{
    $database = contactApprovalDatabase();
    $owner = contactApprovalOwner();
    $action = $input['action'];
    if ($action === 'request_contact_approval') {
        $purpose = $input['purpose'] ?? '';
        $ids = $input['ids'] ?? null;
        if (!in_array($purpose, ['view', 'excel'], true) || !is_array($ids) || count($ids) < 1 || count($ids) > 500) respond(422, ['error' => '조회 또는 Excel 용도로 1~500개 기록을 선택해 주세요.']);
        foreach ($ids as $id) if (!is_int($id) || $id < 1) respond(422, ['error' => '기록 번호가 올바르지 않습니다.']);
        $ids = array_values(array_unique($ids));
        try { $mailConfig = approvalMailConfig(); }
        catch (RuntimeException $error) { respond(503, ['error' => $error->getMessage()]); }
        $records = contactApprovalRecords($database, $ids);
        if (count($records) !== count($ids)) respond(409, ['error' => '조회 목록이 변경되었습니다. 새로고침 후 요청해 주세요.']);
        $database->beginTransaction();
        // The first write serializes rate-limit checks across sessions.
        $database->exec('DELETE FROM contact_approvals WHERE expires_at < ' . (time() - 86400));
        $rate = $database->prepare('SELECT COUNT(*) FROM contact_approvals WHERE created_at > ?');
        $rate->execute([time() - 60]);
        $recent = $database->prepare('SELECT COUNT(*) FROM contact_approvals WHERE owner = ? AND created_at > ?');
        $recent->execute([$owner, time() - 60]);
        if ((int) $rate->fetchColumn() >= 5 || (int) $recent->fetchColumn() > 0) {
            $database->rollBack();
            respond(429, ['error' => '요청이 많습니다. 1분 후 다시 시도해 주세요.']);
        }
        $id = bin2hex(random_bytes(16));
        $token = bin2hex(random_bytes(32));
        $insert = $database->prepare('INSERT INTO contact_approvals (id, owner, purpose, record_ids, snapshot_hash, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
        $insert->execute([$id, $owner, $purpose, json_encode($ids), contactSnapshotHash($records), hash('sha256', $token), time(), time() + 900]);
        $database->commit();
        $label = $purpose === 'view' ? '웹 조회 1회' : 'Excel 추출 1회';
        $link = $mailConfig['base'] . '/approve-contacts.php#token=' . $token;
        $subject = '[설치 정보] 담당자 개인정보 공개 승인 요청';
        $message = "pantech 로그인 사용자가 담당자 이름과 연락처 공개를 요청했습니다.\n용도: {$label}\n기록 수: " . count($ids) . "\n요청 번호: {$id}\n\n아래 링크에서 내용을 확인하고 ‘인증 완료’를 클릭해 주세요.\n{$link}\n\n15분 이내 승인 및 사용이 필요하며, 해당 로그인 세션에서 1회만 사용할 수 있습니다.\n요청하지 않은 공개는 승인하지 마세요.";
        $sent = sendApprovalMail($mailConfig, CONTACT_APPROVER, $subject, $message);
        if (!$sent) {
            // Keep failed attempts for the rate limit, but make their tokens unusable.
            $database->prepare('UPDATE contact_approvals SET expires_at = ? WHERE id = ?')->execute([time(), $id]);
            respond(503, ['error' => '승인 이메일을 발송하지 못했습니다. 서버 메일 설정을 확인해 주세요.']);
        }
        respond(200, ['request_id' => $id, 'message' => '담당자에게 승인 이메일을 발송했습니다. 15분 이내에 승인 후 1회 사용해 주세요.']);
    }
    $id = $input['request_id'] ?? '';
    if (!is_string($id) || !preg_match('/^[a-f0-9]{32}$/', $id)) respond(422, ['error' => '승인 요청 번호를 확인해 주세요.']);
    $database->beginTransaction();
    $consume = $database->prepare('UPDATE contact_approvals SET consumed_at = ? WHERE id = ? AND owner = ? AND purpose = ? AND approved_at IS NOT NULL AND consumed_at IS NULL AND expires_at > ?');
    $purpose = $input['purpose'] ?? '';
    if (!is_string($purpose)) { $database->rollBack(); respond(422, ['error' => '공개 용도를 확인해 주세요.']); }
    $consume->execute([time(), $id, $owner, $purpose, time()]);
    if ($consume->rowCount() !== 1) { $database->rollBack(); respond(403, ['error' => '담당자 승인이 아직 없거나 만료·사용된 요청입니다. 요청한 로그인 세션과 용도를 확인해 주세요.']); }
    $query = $database->prepare('SELECT * FROM contact_approvals WHERE id = ?');
    $query->execute([$id]);
    $approval = $query->fetch();
    $ids = json_decode($approval['record_ids'], true, 512, JSON_THROW_ON_ERROR);
    $records = contactApprovalRecords($database, $ids);
    if (count($records) !== count($ids) || !hash_equals($approval['snapshot_hash'], contactSnapshotHash($records))) {
        $database->commit();
        respond(409, ['error' => '담당자 정보가 변경되었습니다. 새 승인을 요청해 주세요.']);
    }
    $result = [];
    foreach ($records as $record) $result[] = ['id' => (int) $record['id']] + activityRecordData($record);
    $database->commit();
    // Only this atomic, session-bound consumption endpoint may return unmasked contacts.
    $GLOBALS['approved_contact_response'] = true;
    respond(200, ['records' => $result, 'purpose' => $purpose]);
}
