<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $status, array $payload): void
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

require_once dirname(__DIR__) . '/lib/auth.php';

function readJsonRequest(): array
{
    if (strpos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) {
        respond(415, ['error' => 'JSON 형식의 요청만 처리할 수 있습니다.']);
    }
    $rawInput = file_get_contents('php://input', false, null, 0, 2000001);
    if ($rawInput === false) {
        respond(400, ['error' => '요청 데이터를 읽을 수 없습니다.']);
    }
    if (strlen($rawInput) > 2000000) {
        respond(413, ['error' => '요청 데이터가 너무 큽니다.']);
    }
    try {
        $input = json_decode($rawInput, true, 512, JSON_THROW_ON_ERROR);
    } catch (JsonException $exception) {
        respond(400, ['error' => '요청 데이터를 읽을 수 없습니다.']);
    }
    if (!is_array($input)) {
        respond(400, ['error' => '요청 데이터 형식이 올바르지 않습니다.']);
    }
    return $input;
}

function connectDatabase(): PDO
{
    $dataDirectory = dirname(__DIR__) . '/data';
    if (!is_dir($dataDirectory) && !@mkdir($dataDirectory, 0770, true) && !is_dir($dataDirectory)) {
        throw new RuntimeException('데이터 저장 디렉터리를 만들 수 없습니다.');
    }

    $database = new PDO('sqlite:' . $dataDirectory . '/installed-management.sqlite');
    $database->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $database->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $database->exec('PRAGMA busy_timeout = 5000');
    $database->exec(
        'CREATE TABLE IF NOT EXISTS devices (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_date TEXT NOT NULL,
            device_name TEXT NOT NULL,
            existing_version TEXT NOT NULL,
            upgrade_version TEXT NOT NULL,
            rack_count INTEGER NOT NULL CHECK (rack_count BETWEEN 1 AND 100),
            module_counts TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )'
    );
    $recordColumns = $database->query('PRAGMA table_info(records)')->fetchAll();
    $existingColumns = array_column($recordColumns, 'name');
    $additionalColumns = [
        'door_existing_version' => "TEXT NOT NULL DEFAULT ''",
        'door_upgrade_version' => "TEXT NOT NULL DEFAULT ''",
        'rack_names' => "TEXT NOT NULL DEFAULT '[]'",
        'site_name' => "TEXT NOT NULL DEFAULT ''",
        'address' => "TEXT NOT NULL DEFAULT ''",
        'contacts_json' => "TEXT NOT NULL DEFAULT '[]'",
        'notes' => "TEXT NOT NULL DEFAULT ''",
        'work_status' => "TEXT NOT NULL DEFAULT '방문예정'",
        'work_status_other' => "TEXT NOT NULL DEFAULT ''",
    ];
    foreach ($additionalColumns as $column => $definition) {
        if (!in_array($column, $existingColumns, true)) {
            $database->exec("ALTER TABLE records ADD COLUMN {$column} {$definition}");
        }
    }
    $database->exec(
        'CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK (action IN (\'create\', \'update\', \'delete\')),
            summary TEXT NOT NULL,
            details TEXT NOT NULL,
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )'
    );
    $database->exec(
        'CREATE INDEX IF NOT EXISTS idx_activity_log_occurred_at ON activity_log (occurred_at)'
    );
    $database->exec("DELETE FROM activity_log WHERE occurred_at < datetime('now', '-1 year')");

    $seedDevice = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
    foreach (['SMU02C + Door LCD', 'Door LCD', 'iIoT Gateway', 'SMU02C'] as $deviceName) {
        $seedDevice->execute([$deviceName]);
    }

    return $database;
}

function isValidDate(string $value): bool
{
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value);
    return $date !== false && $date->format('Y-m-d') === $value;
}

function isListArray(array $value): bool
{
    return $value === [] || array_keys($value) === range(0, count($value) - 1);
}

function decodedRackNames(array $record): array
{
    $names = $record['rack_names'] ?? [];
    if (is_string($names)) {
        $names = json_decode($names, true, 512, JSON_THROW_ON_ERROR);
    }
    $result = [];
    for ($index = 0; $index < (int) $record['rack_count']; $index++) {
        $result[] = $names[$index] ?? sprintf('Rack %02d', $index + 1);
    }
    return $result;
}

function activityRecordData(array $record): array
{
    $moduleCounts = $record['module_counts'];
    if (is_string($moduleCounts)) {
        $moduleCounts = json_decode($moduleCounts, true, 512, JSON_THROW_ON_ERROR);
    }
    $contacts = $record['contacts_json'] ?? $record['contacts'] ?? [];
    if (is_string($contacts)) {
        $contacts = json_decode($contacts, true, 512, JSON_THROW_ON_ERROR);
    }

    return [
        'visit_date' => $record['visit_date'],
        'device_name' => $record['device_name'],
        'existing_version' => $record['existing_version'],
        'upgrade_version' => $record['upgrade_version'],
        'door_existing_version' => $record['door_existing_version'] ?? '',
        'door_upgrade_version' => $record['door_upgrade_version'] ?? '',
        'rack_count' => (int) $record['rack_count'],
        'module_counts' => array_values($moduleCounts),
        'rack_names' => decodedRackNames($record),
        'site_name' => $record['site_name'] ?? '',
        'address' => $record['address'] ?? '',
        'contacts' => array_values($contacts),
        'notes' => $record['notes'] ?? '',
        'work_status' => $record['work_status'] ?? '방문예정',
        'work_status_other' => $record['work_status_other'] ?? '',
    ];
}

function recordActivity(PDO $database, string $action, int $recordId, array $record, array $details = []): void
{
    $recordData = activityRecordData($record);
    $summary = sprintf(
        '%s · %s · %s → %s',
        $recordData['visit_date'],
        $recordData['device_name'],
        $recordData['existing_version'],
        $recordData['upgrade_version']
    );
    $auditDetails = ['record' => $recordData] + $details;
    $insert = $database->prepare(
        'INSERT INTO activity_log (record_id, action, summary, details) VALUES (?, ?, ?, ?)'
    );
    $insert->execute([
        $recordId,
        $action,
        $summary,
        json_encode($auditDetails, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR),
    ]);
}

function loadData(PDO $database, array $filters): array
{
    [$conditions, $parameters] = filterConditions($filters);

    $sql = 'SELECT id, visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version,
                   rack_count, module_counts, rack_names, site_name, address, contacts_json, notes,
                   work_status, work_status_other, created_at
            FROM records';
    if ($conditions !== []) {
        $sql .= ' WHERE ' . implode(' AND ', $conditions);
    }
    $sql .= ' ORDER BY visit_date DESC, id DESC';

    $recordQuery = $database->prepare($sql);
    $recordQuery->execute($parameters);
    $records = $recordQuery->fetchAll();

    foreach ($records as &$record) {
        $record['id'] = (int) $record['id'];
        $record['rack_count'] = (int) $record['rack_count'];
        $record['module_counts'] = json_decode($record['module_counts'], true, 512, JSON_THROW_ON_ERROR);
        $record['rack_names'] = decodedRackNames($record);
        $record['contacts'] = json_decode($record['contacts_json'], true, 512, JSON_THROW_ON_ERROR);
        unset($record['contacts_json']);
    }
    unset($record);

    $devices = $database->query('SELECT name FROM devices ORDER BY CASE name WHEN \'SMU02C + Door LCD\' THEN 0 WHEN \'Door LCD\' THEN 1 WHEN \'iIoT Gateway\' THEN 2 WHEN \'SMU02C\' THEN 3 ELSE 4 END, name COLLATE NOCASE')->fetchAll(PDO::FETCH_COLUMN);
    $currentVersions = $database->query(
        'SELECT DISTINCT upgrade_version FROM records ORDER BY upgrade_version COLLATE NOCASE'
    )->fetchAll(PDO::FETCH_COLUMN);
    $existingVersions = $database->query(
        'SELECT DISTINCT existing_version FROM records ORDER BY existing_version COLLATE NOCASE'
    )->fetchAll(PDO::FETCH_COLUMN);
    $upgradeVersions = $currentVersions;
    $inputHistory = $database->query(
        'SELECT id, visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version,
                rack_count, module_counts, rack_names, site_name, address, contacts_json, notes,
                work_status, work_status_other
         FROM records
         ORDER BY visit_date DESC, id DESC
         LIMIT 100'
    )->fetchAll();

    foreach ($inputHistory as &$record) {
        $record['id'] = (int) $record['id'];
        $record['rack_count'] = (int) $record['rack_count'];
        $record['module_counts'] = json_decode($record['module_counts'], true, 512, JSON_THROW_ON_ERROR);
        $record['rack_names'] = decodedRackNames($record);
        $record['contacts'] = json_decode($record['contacts_json'], true, 512, JSON_THROW_ON_ERROR);
        unset($record['contacts_json']);
    }
    unset($record);

    return [
        'records' => $records,
        'devices' => $devices,
        'current_versions' => $currentVersions,
        'existing_versions' => $existingVersions,
        'upgrade_versions' => $upgradeVersions,
        'input_history' => $inputHistory,
    ];
}

function validatedFilters(array $source): array
{
    $dateMode = $source['date_mode'] ?? 'all';
    if (!is_string($dateMode) || !in_array($dateMode, ['day', 'range', 'all'], true)) {
        respond(422, ['error' => '조회 기간 선택을 확인해 주세요.']);
    }

    $filters = [
        'date_mode' => $dateMode,
        'date' => '',
        'start_date' => '',
        'end_date' => '',
        'device' => $source['device'] ?? '',
        'version' => $source['version'] ?? '',
    ];
    if ($dateMode === 'day') {
        $filters['date'] = $source['date'] ?? '';
        if (!is_string($filters['date']) || !isValidDate($filters['date'])) {
            respond(422, ['error' => '조회 날짜를 선택해 주세요.']);
        }
    } elseif ($dateMode === 'range') {
        $filters['start_date'] = $source['start_date'] ?? '';
        $filters['end_date'] = $source['end_date'] ?? '';
        if (!is_string($filters['start_date']) || !isValidDate($filters['start_date']) ||
            !is_string($filters['end_date']) || !isValidDate($filters['end_date'])) {
            respond(422, ['error' => '시작 날짜와 끝 날짜를 선택해 주세요.']);
        }
        if ($filters['start_date'] > $filters['end_date']) {
            respond(422, ['error' => '시작 날짜는 끝 날짜보다 늦을 수 없습니다.']);
        }
    }

    $deviceLength = is_string($filters['device']) ? preg_match_all('/./us', $filters['device']) : false;
    $versionLength = is_string($filters['version']) ? preg_match_all('/./us', $filters['version']) : false;
    if ($deviceLength === false || $deviceLength > 100 ||
        $versionLength === false || $versionLength > 50) {
        respond(422, ['error' => '장비명 또는 버전 필터를 확인해 주세요.']);
    }
    return $filters;
}

function filterConditions(array $filters): array
{
    $conditions = [];
    $parameters = [];
    if ($filters['date_mode'] === 'day') {
        $conditions[] = 'visit_date = ?';
        $parameters[] = $filters['date'];
    } elseif ($filters['date_mode'] === 'range') {
        $conditions[] = 'visit_date BETWEEN ? AND ?';
        $parameters[] = $filters['start_date'];
        $parameters[] = $filters['end_date'];
    }
    if ($filters['device'] !== '') {
        $conditions[] = 'device_name = ?';
        $parameters[] = $filters['device'];
    }
    if ($filters['version'] !== '') {
        $conditions[] = 'upgrade_version = ?';
        $parameters[] = $filters['version'];
    }
    return [$conditions, $parameters];
}

function requiredText(array $input, string $key, int $maxLength): string
{
    $value = $input[$key] ?? null;
    if (!is_string($value)) {
        respond(422, ['error' => '필수 항목을 입력해 주세요.']);
    }

    $value = trim($value);
    $length = preg_match_all('/./us', $value);
    if ($value === '' || $length === false || $length > $maxLength) {
        respond(422, ['error' => '입력 항목이 비어 있거나 허용 길이를 초과했습니다.']);
    }

    return $value;
}

function validateAdditionalFields(array $input): array
{
    $errors = [];
    $rackNames = $input['rack_names'] ?? null;
    $rackCount = $input['rack_count'] ?? 0;
    $normalizedNames = [];
    if ($rackNames !== null &&
        (!is_array($rackNames) || !isListArray($rackNames) || count($rackNames) !== $rackCount)) {
        $errors[] = 'Rack 이름은 Rack 수와 같은 개수로 입력해 주세요.';
    } elseif (is_int($rackCount) && $rackCount >= 1 && $rackCount <= 100) {
        for ($index = 0; $index < $rackCount; $index++) {
            $name = $rackNames[$index] ?? '';
            if (!is_string($name)) {
                $errors[] = 'Rack 이름은 문자로 입력해 주세요.';
                continue;
            }
            $name = trim($name);
            $length = preg_match_all('/./us', $name);
            if ($length === false || $length > 100) {
                $errors[] = 'Rack 이름은 100자 이내로 입력해 주세요.';
            }
            $normalizedNames[] = $name === '' ? sprintf('Rack %02d', $index + 1) : $name;
        }
    }
    $fields = [
        'door_existing_version' => ['Door LCD 기존 설치 버전', 50],
        'door_upgrade_version' => ['Door LCD 업그레이드 버전', 50],
        'site_name' => ['설치장소(국소)', 100],
        'address' => ['주소', 300],
        'notes' => ['비고', 2000],
        'work_status_other' => ['기타 작업상태', 100],
    ];
    $record = ['rack_names' => $normalizedNames];
    foreach ($fields as $key => [$label, $maxLength]) {
        $value = $input[$key] ?? '';
        if (!is_string($value)) {
            $errors[] = $label . ' 입력 형식이 올바르지 않습니다.';
            $record[$key] = '';
            continue;
        }
        $value = trim($value);
        $length = preg_match_all('/./us', $value);
        if ($length === false || $length > $maxLength) {
            $errors[] = $label . '은(는) ' . $maxLength . '자 이내로 입력해 주세요.';
        }
        $record[$key] = $value;
    }

    foreach (['door_existing_version', 'door_upgrade_version'] as $key) {
        if (($input['device_name'] ?? '') === 'SMU02C + Door LCD') {
            if ($record[$key] === '') $errors[] = $fields[$key][0] . '을(를) 입력해 주세요.';
        } else {
            $record[$key] = '';
        }
    }

    $workStatus = $input['work_status'] ?? '방문예정';
    $allowedStatuses = ['방문예정', '작업완료', '작업실패', '작업보류', '기타'];
    if (!is_string($workStatus) || !in_array($workStatus, $allowedStatuses, true)) {
        $errors[] = '작업상태를 목록에서 선택해 주세요.';
        $workStatus = '방문예정';
    }
    if ($workStatus === '기타' && $record['work_status_other'] === '') {
        $errors[] = '기타 작업상태 내용을 입력해 주세요.';
    }
    if ($workStatus !== '기타') {
        $record['work_status_other'] = '';
    }
    $record['work_status'] = $workStatus;

    $contacts = $input['contacts'] ?? [];
    if (!is_array($contacts) || !isListArray($contacts) || count($contacts) > 20) {
        $errors[] = '담당자는 최대 20명까지 입력할 수 있습니다.';
        $contacts = [];
    }
    $record['contacts'] = [];
    foreach ($contacts as $index => $contact) {
        if (!is_array($contact)) {
            $errors[] = '담당자 ' . ($index + 1) . ' 정보 형식이 올바르지 않습니다.';
            continue;
        }
        $name = $contact['name'] ?? '';
        $phone = $contact['phone'] ?? '';
        if (!is_string($name) || !is_string($phone)) {
            $errors[] = '담당자 이름과 연락처는 문자로 입력해 주세요.';
            continue;
        }
        $name = trim($name);
        $phone = trim($phone);
        $nameLength = preg_match_all('/./us', $name);
        $phoneLength = preg_match_all('/./us', $phone);
        if ($name === '' && $phone === '') {
            continue;
        }
        if ($name === '' || $phone === '') {
            $errors[] = '담당자 이름과 연락처를 함께 입력해 주세요.';
            continue;
        }
        if ($nameLength === false || $nameLength > 100 || $phoneLength === false || $phoneLength > 50) {
            $errors[] = '담당자 이름은 100자, 연락처는 50자 이내로 입력해 주세요.';
            continue;
        }
        $record['contacts'][] = ['name' => $name, 'phone' => $phone];
    }

    return ['record' => $record, 'errors' => $errors];
}

function validateBulkRecord($input): array
{
    if (!is_array($input)) {
        return ['record' => null, 'errors' => ['행 데이터 형식이 올바르지 않습니다.']];
    }

    $errors = [];
    $textFields = [
        'visit_date' => ['현장방문날짜', 10],
        'device_name' => ['장비명', 100],
        'existing_version' => ['기존 설치 버전', 50],
        'upgrade_version' => ['업그레이드 버전', 50],
    ];
    $record = [];

    foreach ($textFields as $key => [$label, $maxLength]) {
        $value = $input[$key] ?? null;
        if (!is_string($value)) {
            $errors[] = $label . '을(를) 입력해 주세요.';
            $record[$key] = '';
            continue;
        }
        $value = trim($value);
        $length = preg_match_all('/./us', $value);
        if ($value === '' || $length === false || $length > $maxLength) {
            $errors[] = $label . '이(가) 비어 있거나 허용 길이를 초과했습니다.';
        }
        $record[$key] = $value;
    }

    if ($record['visit_date'] !== '' && !isValidDate($record['visit_date'])) {
        $errors[] = '현장방문날짜는 YYYY-MM-DD 형식이어야 합니다.';
    }

    $rackCount = $input['rack_count'] ?? null;
    $moduleCounts = $input['module_counts'] ?? null;
    if (!is_int($rackCount) || $rackCount < 1 || $rackCount > 100) {
        $errors[] = 'Rack 수는 1~100 사이의 정수여야 합니다.';
    }
    if (!is_array($moduleCounts)) {
        $errors[] = 'Rack별 모듈 수 목록을 확인해 주세요.';
        $moduleCounts = [];
    } else {
        if (!isListArray($moduleCounts)) {
            $errors[] = 'Rack별 모듈 수는 Rack 순서대로 입력해야 합니다.';
        }
        if (is_int($rackCount) && count($moduleCounts) !== $rackCount) {
            $errors[] = 'Rack 수와 Rack별 모듈 수의 개수가 일치해야 합니다.';
        }
    }
    foreach ($moduleCounts as $moduleCount) {
        if (!is_int($moduleCount) || $moduleCount < 1 || $moduleCount > 10) {
            $errors[] = '각 Rack의 모듈 수는 1~10 사이의 정수여야 합니다.';
            break;
        }
    }

    $additional = validateAdditionalFields($input);
    $errors = array_merge($errors, $additional['errors']);
    $record = array_merge($record, $additional['record']);
    $record['rack_count'] = $rackCount;
    $record['module_counts'] = $moduleCounts;
    return ['record' => $record, 'errors' => $errors];
}

try {
    startAppSession();
    $requestAction = $_GET['action'] ?? '';
    if ($_SERVER['REQUEST_METHOD'] === 'GET' && $requestAction === 'session') {
        ensurePasswordHash();
        respond(200, [
            'authenticated' => isAppAuthenticated(),
            'csrf_token' => isAppAuthenticated() ? csrfToken() : null,
        ]);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $requestInput = readJsonRequest();
        $requestAction = $requestInput['action'] ?? '';
        if ($requestAction === 'login') {
            $password = $requestInput['password'] ?? null;
            $passwordHash = ensurePasswordHash();
            if (!is_string($password) || strlen($password) > 72 ||
                !password_verify($password, $passwordHash)) {
                respond(401, ['error' => '암호가 올바르지 않습니다.']);
            }
            session_regenerate_id(true);
            $_SESSION['app_authenticated'] = true;
            unset($_SESSION['app_csrf_token']);
            respond(200, ['csrf_token' => csrfToken()]);
        }

        if (!isAppAuthenticated()) {
            respond(401, ['error' => '로그인이 필요합니다.']);
        }
        verifyCsrfToken();
        if ($requestAction === 'logout') {
            $_SESSION = [];
            session_regenerate_id(true);
            respond(200, ['logged_out' => true]);
        }
    } elseif (!isAppAuthenticated()) {
        respond(401, ['error' => '로그인이 필요합니다.']);
    }

    $database = connectDatabase();

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        if (($_GET['action'] ?? '') === 'activity') {
            $activityQuery = $database->query(
                "SELECT id, record_id, action, summary, details, occurred_at
                 FROM activity_log
                 WHERE occurred_at >= datetime('now', '-1 year')
                 ORDER BY occurred_at DESC, id DESC"
            );
            $activities = $activityQuery->fetchAll();
            foreach ($activities as &$activity) {
                $activity['id'] = (int) $activity['id'];
                $activity['record_id'] = (int) $activity['record_id'];
                $activity['details'] = json_decode($activity['details'], true, 512, JSON_THROW_ON_ERROR);
            }
            unset($activity);
            respond(200, ['activities' => $activities]);
        }
        respond(200, loadData($database, validatedFilters($_GET)));
    }

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        header('Allow: GET, POST');
        respond(405, ['error' => '지원하지 않는 요청입니다.']);
    }

    $input = $requestInput;

    if (($input['action'] ?? '') === 'update_record') {
        $recordId = $input['id'] ?? null;
        if (!is_int($recordId) || $recordId < 1) {
            respond(422, ['error' => '수정할 기록을 확인해 주세요.']);
        }
        $validated = validateBulkRecord($input);
        if ($validated['errors'] !== []) {
            respond(422, ['error' => implode(' ', $validated['errors'])]);
        }

        $database->beginTransaction();
        $exists = $database->prepare(
            'SELECT visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version, rack_count, module_counts, rack_names,
                    site_name, address, contacts_json, notes, work_status, work_status_other
             FROM records WHERE id = ?'
        );
        $exists->execute([$recordId]);
        $oldRecord = $exists->fetch();
        if ($oldRecord === false) {
            $database->rollBack();
            respond(404, ['error' => '수정할 설치 기록을 찾을 수 없습니다. 새로고침 후 다시 시도해 주세요.']);
        }
        $oldRecord = activityRecordData($oldRecord);
        $newRecord = activityRecordData($validated['record']);
        $fieldLabels = [
            'visit_date' => '현장방문날짜',
            'device_name' => '장비명',
            'existing_version' => '기존 설치 버전',
            'upgrade_version' => '업그레이드 버전',
            'door_existing_version' => 'Door LCD 기존 설치 버전',
            'door_upgrade_version' => 'Door LCD 업그레이드 버전',
            'rack_count' => '축전지 Rack 수',
            'module_counts' => 'Rack별 모듈 수',
            'rack_names' => 'Rack 이름',
            'site_name' => '설치장소(국소)',
            'address' => '주소',
            'contacts' => '담당자 정보',
            'notes' => '비고',
            'work_status' => '작업상태',
            'work_status_other' => '기타 작업상태',
        ];
        $changes = [];
        foreach ($fieldLabels as $field => $label) {
            if ($oldRecord[$field] !== $newRecord[$field]) {
                $formatValue = static function ($value): string {
                    if (is_array($value)) {
                        return isset($value[0]['name'])
                            ? implode(', ', array_map(
                                static fn(array $contact): string => $contact['name'] . ' (' . $contact['phone'] . ')',
                                $value
                            ))
                            : implode(', ', $value);
                    }
                    return (string) $value;
                };
                $changes[$label] = [
                    'before' => $formatValue($oldRecord[$field]),
                    'after' => $formatValue($newRecord[$field]),
                ];
            }
        }
        $deviceInsert = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
        $deviceInsert->execute([$validated['record']['device_name']]);
        $recordUpdate = $database->prepare(
            'UPDATE records
             SET visit_date = ?, device_name = ?, existing_version = ?, upgrade_version = ?, door_existing_version = ?, door_upgrade_version = ?,
                 rack_count = ?, module_counts = ?, rack_names = ?, site_name = ?, address = ?, contacts_json = ?,
                 notes = ?, work_status = ?, work_status_other = ?
             WHERE id = ?'
        );
        $recordUpdate->execute([
            $validated['record']['visit_date'],
            $validated['record']['device_name'],
            $validated['record']['existing_version'],
            $validated['record']['upgrade_version'],
            $validated['record']['door_existing_version'],
            $validated['record']['door_upgrade_version'],
            $validated['record']['rack_count'],
            json_encode(array_values($validated['record']['module_counts']), JSON_THROW_ON_ERROR),
            json_encode($validated['record']['rack_names'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
            $validated['record']['site_name'],
            $validated['record']['address'],
            json_encode($validated['record']['contacts'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
            $validated['record']['notes'],
            $validated['record']['work_status'],
            $validated['record']['work_status_other'],
            $recordId,
        ]);
        if ($changes !== []) {
            recordActivity($database, 'update', $recordId, $newRecord, ['changes' => $changes]);
        }
        $database->commit();

        respond(200, ['record_id' => $recordId]);
    }

    if (($input['action'] ?? '') === 'delete_selected') {
        $recordIds = $input['record_ids'] ?? null;
        if (!is_array($recordIds) || !isListArray($recordIds) ||
            count($recordIds) < 1 || count($recordIds) > 5000) {
            respond(422, ['error' => '선택 삭제할 기록을 확인해 주세요. 한 번에 최대 5,000건까지 삭제할 수 있습니다.']);
        }
        foreach ($recordIds as $recordId) {
            if (!is_int($recordId) || $recordId < 1) {
                respond(422, ['error' => '삭제할 기록 번호가 올바르지 않습니다.']);
            }
        }
        $recordIds = array_values(array_unique($recordIds));
        $database->beginTransaction();
        $deletedCount = 0;
        foreach (array_chunk($recordIds, 500) as $idChunk) {
            $placeholders = implode(',', array_fill(0, count($idChunk), '?'));
            $recordsQuery = $database->prepare(
                'SELECT id, visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version,
                        rack_count, module_counts, rack_names, site_name, address, contacts_json, notes,
                        work_status, work_status_other
                 FROM records WHERE id IN (' . $placeholders . ')'
            );
            $recordsQuery->execute($idChunk);
            $recordsToDelete = $recordsQuery->fetchAll();
            foreach ($recordsToDelete as $record) {
                recordActivity($database, 'delete', (int) $record['id'], $record);
            }
            $delete = $database->prepare('DELETE FROM records WHERE id IN (' . $placeholders . ')');
            $delete->execute($idChunk);
            $deletedCount += $delete->rowCount();
        }
        $database->commit();

        respond(200, ['deleted_count' => $deletedCount]);
    }

    if (($input['action'] ?? '') === 'delete_filtered') {
        if (!is_array($input['filters'] ?? null)) {
            respond(422, ['error' => '현재 조회 조건을 확인한 뒤 다시 시도해 주세요.']);
        }
        $filters = validatedFilters($input['filters']);
        [$conditions, $parameters] = filterConditions($filters);
        $sql = 'DELETE FROM records';
        $selectSql = 'SELECT id, visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version,
                             rack_count, module_counts, rack_names, site_name, address, contacts_json, notes,
                             work_status, work_status_other FROM records';
        if ($conditions !== []) {
            $sql .= ' WHERE ' . implode(' AND ', $conditions);
            $selectSql .= ' WHERE ' . implode(' AND ', $conditions);
        }
        $database->beginTransaction();
        $recordsQuery = $database->prepare($selectSql);
        $recordsQuery->execute($parameters);
        foreach ($recordsQuery->fetchAll() as $record) {
            recordActivity($database, 'delete', (int) $record['id'], $record);
        }
        $delete = $database->prepare($sql);
        $delete->execute($parameters);
        $deletedCount = $delete->rowCount();
        $database->commit();

        respond(200, ['deleted_count' => $deletedCount]);
    }

    if (($input['action'] ?? '') === 'bulk_create') {
        $records = $input['records'] ?? null;
        if (!is_array($records) || count($records) < 1 || count($records) > 100 ||
            !isListArray($records)) {
            respond(422, ['error' => '한 번에 1~100개 현장 기록만 등록할 수 있습니다.']);
        }

        $validatedRecords = [];
        $rowErrors = [];
        foreach (array_values($records) as $index => $row) {
            $validated = validateBulkRecord($row);
            if ($validated['errors'] !== []) {
                $sourceRow = is_array($row) && isset($row['source_row']) &&
                    is_int($row['source_row']) && $row['source_row'] >= 2
                    ? $row['source_row']
                    : $index + 2;
                $rowErrors[] = [
                    'row' => $sourceRow,
                    'messages' => $validated['errors'],
                ];
            } else {
                $validatedRecords[] = $validated['record'];
            }
        }
        if ($rowErrors !== []) {
            respond(422, [
                'error' => '입력값을 확인해 주세요. 오류가 있는 행은 저장되지 않았습니다.',
                'row_errors' => $rowErrors,
            ]);
        }

        $database->beginTransaction();
        $deviceInsert = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
        $recordInsert = $database->prepare(
            'INSERT INTO records (
                visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version, rack_count, module_counts, rack_names,
                site_name, address, contacts_json, notes, work_status, work_status_other
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        );
        foreach ($validatedRecords as $record) {
            $deviceInsert->execute([$record['device_name']]);
            $recordInsert->execute([
                $record['visit_date'],
                $record['device_name'],
                $record['existing_version'],
                $record['upgrade_version'],
                $record['door_existing_version'],
                $record['door_upgrade_version'],
                $record['rack_count'],
                json_encode(array_values($record['module_counts']), JSON_THROW_ON_ERROR),
                json_encode($record['rack_names'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
                $record['site_name'],
                $record['address'],
                json_encode($record['contacts'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
                $record['notes'],
                $record['work_status'],
                $record['work_status_other'],
            ]);
            recordActivity(
                $database,
                'create',
                (int) $database->lastInsertId(),
                $record
            );
        }
        $database->commit();

        respond(201, ['created_count' => count($validatedRecords)]);
    }

    $visitDate = requiredText($input, 'visit_date', 10);
    if (!isValidDate($visitDate)) {
        respond(422, ['error' => '현장방문날짜를 확인해 주세요.']);
    }

    $deviceName = requiredText($input, 'device_name', 100);
    $existingVersion = requiredText($input, 'existing_version', 50);
    $upgradeVersion = requiredText($input, 'upgrade_version', 50);
    $rackCount = $input['rack_count'] ?? null;
    $moduleCounts = $input['module_counts'] ?? null;

    if (!is_int($rackCount) || $rackCount < 1 || $rackCount > 100 ||
        !is_array($moduleCounts) || count($moduleCounts) !== $rackCount) {
        respond(422, ['error' => 'Rack 수는 1~100개로 설정하고 각 Rack의 모듈 수를 선택해 주세요.']);
    }
    foreach ($moduleCounts as $moduleCount) {
        if (!is_int($moduleCount) || $moduleCount < 1 || $moduleCount > 10) {
            respond(422, ['error' => '각 Rack의 모듈 수는 1~10대여야 합니다.']);
        }
    }

    $additional = validateAdditionalFields($input);
    if ($additional['errors'] !== []) {
        respond(422, ['error' => implode(' ', $additional['errors'])]);
    }
    $record = array_merge([
        'visit_date' => $visitDate,
        'device_name' => $deviceName,
        'existing_version' => $existingVersion,
        'upgrade_version' => $upgradeVersion,
        'door_existing_version' => $additional['record']['door_existing_version'],
        'door_upgrade_version' => $additional['record']['door_upgrade_version'],
        'rack_count' => $rackCount,
        'module_counts' => $moduleCounts,
    ], $additional['record']);

    $database->beginTransaction();
    $deviceInsert = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
    $deviceInsert->execute([$deviceName]);

    $recordInsert = $database->prepare(
        'INSERT INTO records (
            visit_date, device_name, existing_version, upgrade_version, door_existing_version, door_upgrade_version, rack_count, module_counts, rack_names,
            site_name, address, contacts_json, notes, work_status, work_status_other
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    );
    $recordInsert->execute([
        $visitDate,
        $deviceName,
        $existingVersion,
        $upgradeVersion,
        $record['door_existing_version'],
        $record['door_upgrade_version'],
        $rackCount,
        json_encode(array_values($moduleCounts), JSON_THROW_ON_ERROR),
        json_encode($record['rack_names'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
        $record['site_name'],
        $record['address'],
        json_encode($record['contacts'], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
        $record['notes'],
        $record['work_status'],
        $record['work_status_other'],
    ]);
    $recordId = (int) $database->lastInsertId();
    recordActivity($database, 'create', $recordId, [
        'visit_date' => $visitDate,
        'device_name' => $deviceName,
        'existing_version' => $existingVersion,
        'upgrade_version' => $upgradeVersion,
        'door_existing_version' => $additional['record']['door_existing_version'],
        'door_upgrade_version' => $additional['record']['door_upgrade_version'],
        'rack_count' => $rackCount,
        'module_counts' => $moduleCounts,
        'site_name' => $record['site_name'],
        'address' => $record['address'],
        'contacts' => $record['contacts'],
        'rack_names' => $record['rack_names'],
        'notes' => $record['notes'],
        'work_status' => $record['work_status'],
        'work_status_other' => $record['work_status_other'],
    ]);
    $database->commit();

    respond(201, ['record_id' => $recordId]);
} catch (PDOException $exception) {
    if (isset($database) && $database->inTransaction()) {
        $database->rollBack();
    }
    error_log('Installed Management Version database error: ' . $exception->getMessage());
    respond(500, ['error' => '기록을 저장하거나 불러오지 못했습니다. 서버 관리자에게 문의해 주세요.']);
} catch (Throwable $exception) {
    if (isset($database) && $database instanceof PDO && $database->inTransaction()) {
        $database->rollBack();
    }
    error_log('Installed Management Version error: ' . $exception->getMessage());
    respond(500, ['error' => '요청을 처리하지 못했습니다. 서버 관리자에게 문의해 주세요.']);
}
