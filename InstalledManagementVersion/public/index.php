<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#f4f7fb">
    <title>현장 설치 버전관리</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/app.js" defer></script>
</head>
<body>
    <main class="page-shell">
        <header class="page-header">
            <div class="brand-mark" aria-hidden="true">IM</div>
            <div>
                <p class="eyebrow">FIELD SERVICE · VERSION LOG</p>
                <h1>현장 설치 버전관리</h1>
                <p class="subtitle">현장 장비의 설치 버전과 랙 구성을 기록합니다.</p>
            </div>
        </header>

        <nav class="main-tabs" role="tablist" aria-label="설치 정보 메뉴">
            <button id="entryTab" class="main-tab is-active" type="button" role="tab"
                    aria-selected="true" aria-controls="entryPanel">
                <span class="tab-icon" aria-hidden="true">＋</span>
                설치 정보 입력
            </button>
            <button id="queryTab" class="main-tab" type="button" role="tab"
                    aria-selected="false" aria-controls="queryPanel" tabindex="-1">
                <span class="tab-icon" aria-hidden="true">⌕</span>
                설치 정보 조회
            </button>
        </nav>

        <section id="entryPanel" class="tab-panel panel form-panel" role="tabpanel"
                 aria-labelledby="entryTab">
            <div class="section-heading">
                <div>
                    <p class="eyebrow">NEW FIELD RECORD</p>
                    <h2 id="form-title">설치 정보 입력</h2>
                </div>
                <span class="required-note"><span aria-hidden="true">*</span> 필수 입력</span>
            </div>

            <label class="field previous-record-field">
                <span>이전 입력 불러오기</span>
                <select id="previousRecordSelect">
                    <option value="">최근 입력한 기록을 선택하면 항목을 자동으로 채웁니다</option>
                </select>
            </label>

            <form id="recordForm">
                <div class="form-grid">
                    <label class="field">
                        <span>현장방문날짜 <span class="required" aria-hidden="true">*</span></span>
                        <input id="visitDate" name="visit_date" type="date" required>
                    </label>

                    <label class="field">
                        <span>장비명 <span class="required" aria-hidden="true">*</span></span>
                        <select id="deviceSelect" name="device_name" required>
                            <option value="Door LCD">Door LCD</option>
                            <option value="SMU02C">SMU02C</option>
                            <option value="__new__">+ 새 장치 추가</option>
                        </select>
                    </label>

                    <label class="field custom-device-field" id="customDeviceField" hidden>
                        <span>새 장치명 <span class="required" aria-hidden="true">*</span></span>
                        <input id="customDeviceName" type="text" maxlength="100" autocomplete="off"
                               placeholder="예: Battery Controller">
                    </label>

                    <label class="field">
                        <span>기존 설치 버전 <span class="required" aria-hidden="true">*</span></span>
                        <input id="existingVersion" name="existing_version" type="text" maxlength="50"
                               list="existingVersionOptions" placeholder="예: v0.0.0.8" required>
                        <datalist id="existingVersionOptions"></datalist>
                    </label>

                    <label class="field">
                        <span>업그레이드 버전 <span class="required" aria-hidden="true">*</span></span>
                        <input id="upgradeVersion" name="upgrade_version" type="text" maxlength="50"
                               list="upgradeVersionOptions" value="v0.0.0.9" placeholder="예: v0.0.0.9" required>
                        <datalist id="upgradeVersionOptions"></datalist>
                    </label>
                </div>

                <section class="rack-section" aria-labelledby="rack-title">
                    <div class="rack-heading">
                        <div>
                            <h3 id="rack-title">축전지 랙 구성</h3>
                            <p>랙별 설치 모듈 수를 선택하세요. 모듈은 랙마다 1~10대입니다.</p>
                        </div>
                        <label class="rack-count-field">
                            <span>랙 수</span>
                            <input id="rackCount" name="rack_count" type="number" min="1" max="100"
                                   step="1" value="1" required>
                        </label>
                    </div>
                    <div id="rackModules" class="rack-list"></div>
                </section>

                <div class="form-footer">
                    <p id="formMessage" class="form-message" role="status" aria-live="polite"></p>
                    <button id="saveButton" class="primary-button" type="submit">
                        <span aria-hidden="true">＋</span> 방문 기록 저장
                    </button>
                </div>
            </form>
        </section>

        <section id="queryPanel" class="tab-panel panel query-panel" role="tabpanel"
                 aria-labelledby="queryTab" hidden>
            <div class="section-heading query-heading">
                <div>
                    <p class="eyebrow">SEARCH FIELD RECORDS</p>
                    <h2 id="history-title">설치 정보 조회</h2>
                    <p id="recordCount" class="record-count">기록을 불러오는 중...</p>
                </div>
                <button id="refreshButton" class="secondary-button" type="button">
                    <span aria-hidden="true">↻</span> 새로고침
                </button>
            </div>

            <div class="filter-panel" aria-label="설치 정보 조회 조건">
                <fieldset class="date-mode-fieldset">
                    <legend>조회 기간</legend>
                    <div class="date-mode-options">
                        <label class="date-mode-option">
                            <input type="radio" name="dateMode" value="day">
                            <span>1일</span>
                        </label>
                        <label class="date-mode-option">
                            <input type="radio" name="dateMode" value="range">
                            <span>기간 (시작~끝)</span>
                        </label>
                        <label class="date-mode-option">
                            <input type="radio" name="dateMode" value="all" checked>
                            <span>전체</span>
                        </label>
                    </div>
                </fieldset>

                <div id="singleDateFields" class="date-input-row" hidden>
                    <label class="field">
                        <span>조회 날짜</span>
                        <input id="filterDate" type="date">
                    </label>
                </div>
                <div id="dateRangeFields" class="date-input-row date-range-row" hidden>
                    <label class="field">
                        <span>시작 날짜</span>
                        <input id="filterStartDate" type="date">
                    </label>
                    <span class="range-separator" aria-hidden="true">~</span>
                    <label class="field">
                        <span>끝 날짜</span>
                        <input id="filterEndDate" type="date">
                    </label>
                </div>

                <div class="filter-grid">
                    <label class="field">
                        <span>장비명</span>
                        <select id="deviceFilter">
                            <option value="">전체 장비</option>
                        </select>
                    </label>
                    <label class="field">
                        <span>현재 설치된 버전</span>
                        <select id="versionFilter">
                            <option value="">전체 버전</option>
                        </select>
                    </label>
                </div>
                <p id="filterMessage" class="filter-message" role="status" aria-live="polite"></p>
            </div>

            <div class="export-panel" aria-label="설치 정보 내보내기">
                <div class="export-controls">
                    <label class="field export-format-field">
                        <span>내보내기 형식</span>
                        <select id="exportFormat">
                            <option value="pdf">PDF 문서</option>
                            <option value="csv">CSV 파일</option>
                            <option value="excel">Excel 통합 문서 (.xlsx)</option>
                        </select>
                    </label>
                    <label id="reportOption" class="report-option" hidden>
                        <input id="reportFormat" type="checkbox">
                        <span class="report-check" aria-hidden="true"></span>
                        <span class="report-copy">
                            <strong>보고서 형식</strong>
                            <small>고객 전달용 요약과 상세 내역을 포함합니다</small>
                        </span>
                    </label>
                    <button id="exportButton" class="primary-button export-button" type="button" disabled>
                        <span aria-hidden="true">↓</span> 내보내기
                    </button>
                </div>
                <p id="exportMessage" class="export-message" role="status" aria-live="polite">
                    현재 조회된 목록을 내보냅니다. PDF 선택 시 CSV 파일도 함께 다운로드됩니다.
                </p>
            </div>

            <div id="historyList" class="history-list" aria-live="polite">
                <p class="empty-state">기록을 불러오는 중입니다.</p>
            </div>
        </section>
        <footer class="page-footer">Installed Management Version</footer>
    </main>
    <section id="printReport" class="print-report" aria-label="설치 버전 내보내기 보고서"></section>
</body>
</html>
