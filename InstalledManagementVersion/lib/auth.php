<?php
declare(strict_types=1);

const DEFAULT_APP_PASSWORD = 'jjh1234';

function startAppSession(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }

    ini_set('session.use_strict_mode', '1');
    $scriptDirectory = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/'));
    $cookiePath = rtrim($scriptDirectory, '/') . '/';
    if ($cookiePath === '//') {
        $cookiePath = '/';
    }
    $isHttps = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off';
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => $cookiePath,
        'secure' => $isHttps,
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    session_start();
}

function passwordHashPath(): string
{
    return dirname(__DIR__) . '/data/password.hash';
}

function ensurePasswordHash(): string
{
    $path = passwordHashPath();
    $dataDirectory = dirname($path);
    if (!is_dir($dataDirectory) && !@mkdir($dataDirectory, 0770, true) && !is_dir($dataDirectory)) {
        throw new RuntimeException('암호 저장 디렉터리를 만들 수 없습니다.');
    }

    if (!is_file($path)) {
        $defaultHash = password_hash(DEFAULT_APP_PASSWORD, PASSWORD_DEFAULT);
        $handle = @fopen($path, 'x');
        if ($handle !== false) {
            $contents = $defaultHash . PHP_EOL;
            $writeSucceeded = false;
            try {
                $writeSucceeded = fwrite($handle, $contents) === strlen($contents) && fflush($handle);
            } finally {
                fclose($handle);
            }
            if (!$writeSucceeded) {
                @unlink($path);
                throw new RuntimeException('기본 암호 해시를 저장할 수 없습니다.');
            }
            if (!chmod($path, 0600)) {
                @unlink($path);
                throw new RuntimeException('암호 파일 권한을 제한할 수 없습니다.');
            }
        } elseif (!is_file($path)) {
            throw new RuntimeException('기본 암호 파일을 만들 수 없습니다.');
        }
    }

    $hash = @file_get_contents($path);
    if ($hash === false || trim($hash) === '') {
        throw new RuntimeException('암호 해시 파일을 읽을 수 없습니다.');
    }
    return trim($hash);
}

function isAppAuthenticated(): bool
{
    return isset($_SESSION['app_authenticated']) && $_SESSION['app_authenticated'] === true;
}

function csrfToken(): string
{
    if (!isset($_SESSION['app_csrf_token']) || !is_string($_SESSION['app_csrf_token'])) {
        $_SESSION['app_csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['app_csrf_token'];
}

function verifyCsrfToken(): void
{
    $providedToken = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    if (!is_string($providedToken) || !hash_equals(csrfToken(), $providedToken)) {
        respond(403, ['error' => '보안 토큰이 만료되었습니다. 페이지를 새로고침한 뒤 다시 로그인해 주세요.']);
    }
}
