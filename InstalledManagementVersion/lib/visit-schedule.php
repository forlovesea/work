<?php
declare(strict_types=1);

function validateVisitSchedule($schedule, string $status, array &$errors): string
{
    $empty = '{"mode":"undecided"}';
    if ($status !== '방문예정') return $empty;
    if (!is_array($schedule) || !in_array($schedule['mode'] ?? '', ['undecided', 'single', 'range'], true)) {
        $errors[] = '방문 일정을 미정, 하루 또는 기간으로 선택해 주세요.';
        return $empty;
    }
    if ($schedule['mode'] === 'undecided') return $empty;
    $start = $schedule['start_date'] ?? '';
    $end = $schedule['mode'] === 'single' ? $start : ($schedule['end_date'] ?? '');
    if (!is_string($start) || !is_string($end) || !isValidDate($start) || !isValidDate($end) || $end < $start) {
        $errors[] = '방문 일정의 시작일과 종료일을 확인해 주세요.';
        return $empty;
    }
    $from = $schedule['start_hour'] ?? null;
    $to = $schedule['end_hour'] ?? null;
    if (($from !== null || $to !== null) && (!is_int($from) || !is_int($to) || $from < 0 || $to > 23 || $to <= $from)) {
        $errors[] = '방문시간은 0~23시로 시작과 종료를 모두 선택하고 종료를 더 늦게 설정해 주세요.';
        return $empty;
    }
    return json_encode(['mode' => $schedule['mode'], 'start_date' => $start, 'end_date' => $end, 'start_hour' => $from, 'end_hour' => $to], JSON_THROW_ON_ERROR);
}
