<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once dirname(__DIR__) . '/lib/auth.php';

function promptPassword(string $prompt): string
{
    $terminal = @fopen('/dev/tty', 'r+');
    if ($terminal === false || !function_exists('exec')) {
        if ($terminal !== false) {
            fclose($terminal);
        }
        throw new RuntimeException('암호를 숨겨 입력할 수 있는 터미널에서 실행해야 합니다.');
    }

    fwrite(STDOUT, $prompt);
    exec('stty -echo < /dev/tty 2>&1', $output, $status);
    if ($status !== 0) {
        fclose($terminal);
        throw new RuntimeException('터미널 입력을 숨길 수 없습니다.');
    }

    try {
        $input = fgets($terminal);
    } finally {
        exec('stty echo < /dev/tty 2>&1', $output, $restoreStatus);
        fwrite(STDOUT, PHP_EOL);
        fclose($terminal);
    }
    if ($restoreStatus !== 0) {
        throw new RuntimeException('터미널 입력 표시를 복구할 수 없습니다.');
    }

    if ($input === false) {
        throw new RuntimeException('암호 입력을 읽을 수 없습니다.');
    }
    return rtrim($input, "\r\n");
}

try {
    $password = promptPassword('새 암호(8~72바이트): ');
    if (strlen($password) < 8 || strlen($password) > 72) {
        throw new RuntimeException('암호는 8~72바이트여야 합니다.');
    }
    $confirmation = promptPassword('새 암호 확인: ');
    if (!hash_equals($password, $confirmation)) {
        throw new RuntimeException('두 번 입력한 암호가 일치하지 않습니다.');
    }

    $path = passwordHashPath();
    $dataDirectory = dirname($path);
    if (!is_dir($dataDirectory)) {
        if (!@mkdir($dataDirectory, 0770, true) && !is_dir($dataDirectory)) {
            throw new RuntimeException('암호 저장 디렉터리를 만들 수 없습니다.');
        }
        if (!chown($dataDirectory, 'www-data') || !chmod($dataDirectory, 0770)) {
            throw new RuntimeException('암호 저장 디렉터리를 www-data에서 사용할 수 있도록 설정하지 못했습니다.');
        }
    }
    $hash = password_hash($password, PASSWORD_DEFAULT);
    $temporaryPath = $path . '.' . bin2hex(random_bytes(8)) . '.tmp';
    $contents = $hash . PHP_EOL;
    if (@file_put_contents($temporaryPath, $contents, LOCK_EX) !== strlen($contents)) {
        @unlink($temporaryPath);
        throw new RuntimeException('새 암호를 임시 파일에 저장할 수 없습니다.');
    }
    if (!chown($temporaryPath, 'www-data')) {
        @unlink($temporaryPath);
        throw new RuntimeException('웹 서버 계정(www-data)으로 암호 파일 소유자를 설정할 수 없습니다. sudo로 실행하세요.');
    }
    if (!chmod($temporaryPath, 0600)) {
        @unlink($temporaryPath);
        throw new RuntimeException('임시 암호 파일 권한을 제한할 수 없습니다.');
    }
    if (!@rename($temporaryPath, $path)) {
        @unlink($temporaryPath);
        throw new RuntimeException('암호 파일을 안전하게 교체할 수 없습니다.');
    }
    if (!chmod($path, 0600)) {
        throw new RuntimeException('암호 파일 권한을 제한할 수 없습니다.');
    }

    fwrite(STDOUT, "암호를 변경했습니다.\n");
} catch (Throwable $exception) {
    fwrite(STDERR, '오류: ' . $exception->getMessage() . PHP_EOL);
    exit(1);
}
