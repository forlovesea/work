let contactPrivacyRestricted = true;
let pendingContactApproval = null;
let contactApprovalBusy = false;
let contactPrivacyGeneration = 0;
let contactRevealTimer;

function closeContactReveal() {
    clearTimeout(contactRevealTimer);
    const dialog = document.getElementById('contactRevealDialog');
    if (dialog) { if (dialog.open) dialog.close(); dialog.remove(); }
}

function setContactPrivacy(restricted) {
    contactPrivacyRestricted = restricted !== false;
    contactPrivacyGeneration++;
    pendingContactApproval = null;
    closeContactReveal();
    document.getElementById('contactPrivacyPanel').hidden = !contactPrivacyRestricted;
    document.getElementById('consumeContactApproval').disabled = true;
}

async function contactApprovalRequest(payload) {
    const response = await authenticatedFetch('api.php', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '승인 요청을 처리하지 못했습니다.');
    return data;
}

function showApprovedContacts(records) {
    closeContactReveal();
    const dialog = document.createElement('dialog');
    dialog.id = 'contactRevealDialog';
    dialog.className = 'contact-reveal-dialog';
    const heading = document.createElement('h2');
    heading.id = 'contactRevealTitle';
    heading.textContent = '승인된 담당자 정보 · 1회 조회';
    dialog.setAttribute('aria-labelledby', heading.id);
    const hint = document.createElement('p');
    hint.textContent = '60초 후 자동으로 닫힙니다. 다시 열거나 Excel로 추출하려면 별도 승인이 필요합니다.';
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '닫기';
    close.addEventListener('click', closeContactReveal);
    dialog.append(heading, hint, close);
    for (const record of records) {
        const line = document.createElement('p');
        line.textContent = `${record.site_name || '설치장소 미입력'} · ${record.device_name}: ${(record.contacts || []).map(contact => `${contact.name} (${contact.phone})`).join(', ') || '담당자 없음'}`;
        dialog.append(line);
    }
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeContactReveal(); });
    document.body.append(dialog);
    dialog.showModal();
    close.focus();
    contactRevealTimer = setTimeout(closeContactReveal, 60_000);
}

document.getElementById('requestContactApproval').addEventListener('click', async () => {
    if (contactApprovalBusy) return;
    const message = document.getElementById('contactApprovalMessage');
    if (isLoadingRecords || !displayedRecords.length || displayedRecords.length > 500) {
        message.textContent = '조회가 완료된 목록 1~500건으로 요청해 주세요.';
        return;
    }
    contactApprovalBusy = true;
    const generation = contactPrivacyGeneration;
    const purpose = document.getElementById('contactApprovalPurpose').value;
    const filename = `${exportBaseName()}_승인1회`;
    document.getElementById('requestContactApproval').disabled = true;
    document.getElementById('consumeContactApproval').disabled = true;
    pendingContactApproval = null;
    try {
        const data = await contactApprovalRequest({ action: 'request_contact_approval', purpose, ids: displayedRecords.map(record => record.id) });
        if (generation !== contactPrivacyGeneration) return;
        pendingContactApproval = { id: data.request_id, purpose, filename };
        message.textContent = data.message + (purpose === 'view' ? ' 웹 조회용입니다.' : ' Excel 추출용입니다.');
    } catch (error) { message.textContent = error.message; }
    finally {
        contactApprovalBusy = false;
        document.getElementById('requestContactApproval').disabled = false;
        document.getElementById('consumeContactApproval').disabled = !pendingContactApproval;
    }
});

document.getElementById('consumeContactApproval').addEventListener('click', async () => {
    if (contactApprovalBusy || !pendingContactApproval) return;
    const approval = pendingContactApproval;
    const generation = contactPrivacyGeneration;
    const message = document.getElementById('contactApprovalMessage');
    contactApprovalBusy = true;
    document.getElementById('consumeContactApproval').disabled = true;
    try {
        const data = await contactApprovalRequest({ action: 'consume_contact_approval', request_id: approval.id, purpose: approval.purpose });
        pendingContactApproval = null;
        if (generation !== contactPrivacyGeneration) return;
        if (approval.purpose === 'view') showApprovedContacts(data.records);
        else {
            // Synchronous export uses approved records only for this file, never the visible list/history.
            const originalRecords = displayedRecords;
            try {
                displayedRecords = data.records;
                exportExcel(approval.filename);
            } finally {
                displayedRecords = originalRecords;
            }
        }
        data.records = [];
        message.textContent = '1회 공개를 사용했습니다. 다시 공개하려면 새 승인이 필요합니다.';
    } catch (error) { message.textContent = error.message; }
    finally {
        contactApprovalBusy = false;
        document.getElementById('consumeContactApproval').disabled = !pendingContactApproval;
    }
});
window.addEventListener('pagehide', closeContactReveal);
document.addEventListener('visibilitychange', () => { if (document.hidden) closeContactReveal(); });
