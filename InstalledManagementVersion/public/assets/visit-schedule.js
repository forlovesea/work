function readVisitSchedule(record) {
    const value = record.visit_schedule;
    return typeof value === 'string' ? JSON.parse(value || '{}') : (value || {});
}

function visitScheduleDisplay(record) {
    if (record.work_status !== '방문예정') return '';
    const schedule = readVisitSchedule(record);
    if (!schedule.mode || schedule.mode === 'undecided') return '일정 미정';
    const dates = schedule.mode === 'single' || schedule.start_date === schedule.end_date
        ? schedule.start_date : `${schedule.start_date} ~ ${schedule.end_date}`;
    const hour = value => `${value < 12 ? '오전' : '오후'} ${value % 12 || 12}시`;
    const hours = schedule.start_hour == null ? '시간 미정'
        : `${hour(schedule.start_hour)} ~ ${hour(schedule.end_hour)}`;
    return `${dates} 방문예정 · ${hours}`;
}

function visitScheduleValue() {
    const mode = document.querySelector('#visitScheduleMode').value;
    if (workStatusInput.value !== '방문예정' || mode === 'undecided') return { mode: 'undecided' };
    const start = document.querySelector('#visitScheduleStart').value;
    const startHour = document.querySelector('#visitStartHour').value;
    const endHour = document.querySelector('#visitEndHour').value;
    return {
        mode, start_date: start,
        end_date: mode === 'single' ? start : document.querySelector('#visitScheduleEnd').value,
        start_hour: startHour === '' ? null : Number(startHour),
        end_hour: endHour === '' ? null : Number(endHour),
    };
}

function updateVisitSchedule() {
    const panel = document.querySelector('#visitSchedule');
    const active = workStatusInput.value === '방문예정';
    const mode = document.querySelector('#visitScheduleMode').value;
    panel.hidden = !active;
    panel.querySelectorAll('input, select').forEach(input => { input.disabled = !active; });
    document.querySelector('#visitScheduleDates').hidden = mode === 'undecided';
    const start = document.querySelector('#visitScheduleStart');
    const end = document.querySelector('#visitScheduleEnd');
    const from = document.querySelector('#visitStartHour');
    const to = document.querySelector('#visitEndHour');
    for (const input of [start, end, from, to]) {
        input.disabled = !active || mode === 'undecided' || (input === end && mode !== 'range');
        input.required = !input.disabled && (input === start || input === end);
        input.setCustomValidity('');
    }
    end.parentElement.hidden = mode !== 'range';
    end.min = start.value;
    if (!end.disabled && end.value && end.value < start.value) end.setCustomValidity('종료일은 시작일 이후로 선택해 주세요.');
    if (!from.disabled) {
        from.required = to.value !== '';
        to.required = from.value !== '';
        if (from.value !== '' && to.value !== '' && Number(to.value) <= Number(from.value)) {
            to.setCustomValidity('종료 시간은 시작 시간보다 늦게 선택해 주세요.');
        }
    }
    document.querySelector('#visitSchedulePreview').textContent = visitScheduleDisplay({ work_status: workStatusInput.value, visit_schedule: visitScheduleValue() });
}

function fillVisitSchedule(record) {
    const schedule = readVisitSchedule(record);
    for (const [id, value] of Object.entries({ visitScheduleMode: schedule.mode || 'undecided', visitScheduleStart: schedule.start_date || '', visitScheduleEnd: schedule.end_date || '', visitStartHour: schedule.start_hour ?? '', visitEndHour: schedule.end_hour ?? '' })) {
        document.getElementById(id).value = value;
    }
}
