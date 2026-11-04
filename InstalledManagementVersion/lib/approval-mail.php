<?php
declare(strict_types=1);

function approvalMailSetting(string $key, string $default = ''): string
{
    $environment = getenv($key);
    if ($environment !== false) return $environment;
    static $configuration;
    if ($configuration === null) {
        $path = getenv('APP_MAIL_CONFIG') ?: '/etc/installed-management/mail.php';
        $configuration = is_file($path) ? require $path : [];
        if (!is_array($configuration)) throw new RuntimeException('메일 설정 파일 형식을 확인해 주세요.');
    }
    return isset($configuration[$key]) && is_scalar($configuration[$key]) ? (string) $configuration[$key] : $default;
}

function approvalMailConfig(): array
{
    $base = rtrim(approvalMailSetting('APP_PUBLIC_URL', approvalMailSetting('PUBLIC_BASE_URL')), '/');
    $parts = parse_url($base);
    if (!filter_var($base, FILTER_VALIDATE_URL) || !$parts || ($parts['scheme'] ?? '') !== 'https' ||
        isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment'])) {
        throw new RuntimeException('설치정보 서비스의 HTTPS 주소(APP_PUBLIC_URL 또는 PUBLIC_BASE_URL)를 설정해 주세요.');
    }
    $host = approvalMailSetting('SMTP_HOST');
    $user = approvalMailSetting('SMTP_USERNAME');
    $password = approvalMailSetting('SMTP_PASSWORD');
    $sender = approvalMailSetting('SMTP_FROM', approvalMailSetting('APP_MAIL_FROM', $user));
    if (!filter_var($sender, FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/', $sender)) throw new RuntimeException('발신 이메일(SMTP_FROM)을 설정해 주세요.');
    $security = approvalMailSetting('SMTP_SECURITY', 'starttls');
    $port = approvalMailSetting('SMTP_PORT', $security === 'ssl' ? '465' : '587');
    if ($host !== '') {
        if (!preg_match('/^[a-zA-Z0-9.-]+$/D', $host) || !ctype_digit($port) || (int) $port < 1 || (int) $port > 65535 ||
            !in_array($security, ['ssl', 'starttls'], true) || (($user === '') !== ($password === ''))) {
            throw new RuntimeException('SMTP 서버, 포트, TLS 방식 및 인증 설정을 확인해 주세요.');
        }
        if (!function_exists('curl_init')) throw new RuntimeException('인증 SMTP 발송을 위해 PHP cURL 확장이 필요합니다.');
    }
    return compact('base', 'host', 'user', 'password', 'sender', 'security', 'port');
}

function sendApprovalMail(array $config, string $recipient, string $subject, string $body): bool
{
    $subject = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    if ($config['host'] === '') {
        return function_exists('mail') && @mail($recipient, $subject, $body, ['From' => $config['sender'], 'Content-Type' => 'text/plain; charset=UTF-8']);
    }
    $message = 'From: ' . $config['sender'] . "\r\nTo: " . $recipient . "\r\nSubject: " . $subject .
        "\r\nDate: " . date(DATE_RFC2822) . "\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" .
        chunk_split(base64_encode($body), 76, "\r\n");
    $offset = 0;
    $curl = curl_init();
    try {
        $options = [
            CURLOPT_URL => ($config['security'] === 'ssl' ? 'smtps://' : 'smtp://') . $config['host'] . ':' . $config['port'],
            CURLOPT_PROTOCOLS => CURLPROTO_SMTP | CURLPROTO_SMTPS,
            CURLOPT_USE_SSL => CURLUSESSL_ALL,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_CONNECTTIMEOUT => 10,
            CURLOPT_TIMEOUT => 20,
            CURLOPT_MAIL_FROM => $config['sender'],
            CURLOPT_MAIL_RCPT => [$recipient],
            CURLOPT_UPLOAD => true,
            CURLOPT_INFILESIZE => strlen($message),
            CURLOPT_READFUNCTION => static function ($handle, $stream, $length) use (&$offset, $message): string {
                $part = substr($message, $offset, $length);
                $offset += strlen($part);
                return $part;
            },
            CURLOPT_RETURNTRANSFER => true,
        ];
        if ($config['user'] !== '') {
            $options[CURLOPT_USERNAME] = $config['user'];
            $options[CURLOPT_PASSWORD] = $config['password'];
        }
        curl_setopt_array($curl, $options);
        return curl_exec($curl) !== false;
    } finally {
        curl_close($curl);
    }
}
