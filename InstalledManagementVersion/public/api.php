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

    $seedDevice = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
    foreach (['Door LCD', 'SMU02C'] as $deviceName) {
        $seedDevice->execute([$deviceName]);
    }

    return $database;
}

function isValidDate(string $value): bool
{
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value);
    return $date !== false && $date->format('Y-m-d') === $value;
}

function loadData(PDO $database, array $filters): array
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

    $sql = 'SELECT id, visit_date, device_name, existing_version, upgrade_version,
                   rack_count, module_counts, created_at
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
    }
    unset($record);

    $devices = $database->query('SELECT name FROM devices ORDER BY name COLLATE NOCASE')->fetchAll(PDO::FETCH_COLUMN);
    $currentVersions = $database->query(
        'SELECT DISTINCT upgrade_version FROM records ORDER BY upgrade_version COLLATE NOCASE'
    )->fetchAll(PDO::FETCH_COLUMN);
    $existingVersions = $database->query(
        'SELECT DISTINCT existing_version FROM records ORDER BY existing_version COLLATE NOCASE'
    )->fetchAll(PDO::FETCH_COLUMN);
    $upgradeVersions = $currentVersions;
    $inputHistory = $database->query(
        'SELECT id, visit_date, device_name, existing_version, upgrade_version,
                rack_count, module_counts
         FROM records
         ORDER BY visit_date DESC, id DESC
         LIMIT 100'
    )->fetchAll();

    foreach ($inputHistory as &$record) {
        $record['id'] = (int) $record['id'];
        $record['rack_count'] = (int) $record['rack_count'];
        $record['module_counts'] = json_decode($record['module_counts'], true, 512, JSON_THROW_ON_ERROR);
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

try {
    $database = connectDatabase();

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $dateMode = $_GET['date_mode'] ?? 'all';
        if (!in_array($dateMode, ['day', 'range', 'all'], true)) {
            respond(422, ['error' => '조회 기간 선택을 확인해 주세요.']);
        }

        $filters = [
            'date_mode' => $dateMode,
            'date' => '',
            'start_date' => '',
            'end_date' => '',
            'device' => '',
            'version' => '',
        ];
        if ($dateMode === 'day') {
            $filters['date'] = $_GET['date'] ?? '';
            if (!is_string($filters['date']) || !isValidDate($filters['date'])) {
                respond(422, ['error' => '조회 날짜를 선택해 주세요.']);
            }
        } elseif ($dateMode === 'range') {
            $filters['start_date'] = $_GET['start_date'] ?? '';
            $filters['end_date'] = $_GET['end_date'] ?? '';
            if (!is_string($filters['start_date']) || !isValidDate($filters['start_date']) ||
                !is_string($filters['end_date']) || !isValidDate($filters['end_date'])) {
                respond(422, ['error' => '시작 날짜와 끝 날짜를 선택해 주세요.']);
            }
            if ($filters['start_date'] > $filters['end_date']) {
                respond(422, ['error' => '시작 날짜는 끝 날짜보다 늦을 수 없습니다.']);
            }
        }
        $filters['device'] = $_GET['device'] ?? '';
        $filters['version'] = $_GET['version'] ?? '';
        $deviceLength = is_string($filters['device']) ? preg_match_all('/./us', $filters['device']) : false;
        $versionLength = is_string($filters['version']) ? preg_match_all('/./us', $filters['version']) : false;
        if ($deviceLength === false || $deviceLength > 100 ||
            $versionLength === false || $versionLength > 50) {
            respond(422, ['error' => '장비명 또는 버전 필터를 확인해 주세요.']);
        }

        respond(200, loadData($database, $filters));
    }

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        header('Allow: GET, POST');
        respond(405, ['error' => '지원하지 않는 요청입니다.']);
    }

    if (strpos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) {
        respond(415, ['error' => 'JSON 형식의 요청만 저장할 수 있습니다.']);
    }

    try {
        $input = json_decode(file_get_contents('php://input'), true, 512, JSON_THROW_ON_ERROR);
    } catch (JsonException $exception) {
        respond(400, ['error' => '요청 데이터를 읽을 수 없습니다.']);
    }

    if (!is_array($input)) {
        respond(400, ['error' => '요청 데이터 형식이 올바르지 않습니다.']);
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
        respond(422, ['error' => '랙 수는 1~100개로 설정하고 각 랙의 모듈 수를 선택해 주세요.']);
    }
    foreach ($moduleCounts as $moduleCount) {
        if (!is_int($moduleCount) || $moduleCount < 1 || $moduleCount > 10) {
            respond(422, ['error' => '각 랙의 모듈 수는 1~10대여야 합니다.']);
        }
    }

    $database->beginTransaction();
    $deviceInsert = $database->prepare('INSERT OR IGNORE INTO devices (name) VALUES (?)');
    $deviceInsert->execute([$deviceName]);

    $recordInsert = $database->prepare(
        'INSERT INTO records (
            visit_date, device_name, existing_version, upgrade_version, rack_count, module_counts
        ) VALUES (?, ?, ?, ?, ?, ?)'
    );
    $recordInsert->execute([
        $visitDate,
        $deviceName,
        $existingVersion,
        $upgradeVersion,
        $rackCount,
        json_encode(array_values($moduleCounts), JSON_THROW_ON_ERROR),
    ]);
    $database->commit();

    respond(201, ['record_id' => (int) $database->lastInsertId()]);
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
