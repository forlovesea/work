// The bearer token stays out of request URLs and server access logs.
const approvalLinkToken = new URLSearchParams(window.location.hash.slice(1)).get('token');
if (approvalLinkToken && /^[a-f0-9]{64}$/.test(approvalLinkToken)) {
    window.history.replaceState(null, '', window.location.pathname);
    const form = document.getElementById('approvalInspect');
    form.elements.token.value = approvalLinkToken;
    form.submit(); // Inspect only; approval requires the explicit confirmation button.
}
