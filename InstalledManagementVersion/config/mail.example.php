<?php
// Copy to /etc/installed-management/mail.php (outside the public directory).
// Reuse the six SMTP_* values from WebConference's /etc/moa/moa.env.
// Do not copy its PUBLIC_BASE_URL: this URL must point to this application.
return [
    'PUBLIC_BASE_URL' => 'https://61.105.141.21/installed-management',
    'SMTP_HOST' => 'smtp.gmail.com',
    'SMTP_PORT' => '587',
    'SMTP_SECURITY' => 'starttls',
    'SMTP_USERNAME' => 'YOUR_SENDER_ACCOUNT@gmail.com',
    'SMTP_PASSWORD' => 'YOUR_APP_PASSWORD',
    'SMTP_FROM' => 'YOUR_SENDER_ACCOUNT@gmail.com',
];
