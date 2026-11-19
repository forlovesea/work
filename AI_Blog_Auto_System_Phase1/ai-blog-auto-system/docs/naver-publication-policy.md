# 네이버 발행 경계

확인일: 2026-11-18. 현재 구현에는 네이버 자동 발행 경로가 없습니다.
`windows-app/blog_gui/manual.py`의 `AUTO_PUBLISH_ENABLED=False`이며 `automatic_publish()`는 항상 거부합니다.
브라우저 자동 조작, 비공식 내부 API, 계정 비밀번호/쿠키 수집, 글쓰기 URL Scheme을 사용하지 않습니다.

공식 근거:

- [블로그 오픈 API 종료 공지](https://developers.naver.com/notice/article/7527): 로그인 방식 블로그 글쓰기 API는 2020-05-06 종료.
- [블로그앱 글쓰기 URL Scheme 지원 종료 공지](https://developers.naver.com/notice/article/8595): 2022-12-23 종료.

허용된 현재 흐름은 콘텐츠 작성·파일 출력 → 사용자가 공식 웹/앱 편집기를 직접 열어 검토·게시 → 앱에서 완료를 신고하는 방식입니다.
완료 신고 URL은 `https://blog.naver.com/...` 또는 `https://m.blog.naver.com/...`만 저장합니다.
서버는 URL을 요청하지 않으며 게시물 실재 여부를 확인하지 않습니다.
URL을 저장했다고 네이버에서 승인한 자동 연동으로 간주하지 않습니다.

로그인 상태는 사용자 신고 이벤트이며 `source=user_report, verified=false`를 명시합니다.
`PUBLISH_FAILED`도 이 통합 흐름에서는 사용자 신고/Mock 장애 주입입니다. 실제 자동 발행을 시도하여 얻은 실패가 아닙니다.
`MANUAL_PUBLISH_COMPLETED`는 `PUBLISH_SUCCESS`와 별도이며 자동 성공 통계에 더하지 않습니다.
서버 완료 API는 명시적 boolean 확인을 요구하고 동일 패키지/URL은 멱등 처리, 다른 URL 재기록은 409로 거부합니다.
최초 완료 신고는 만료 이후 거부합니다. 이미 성공한 동일 신고의 재시도는 만료 후에도 기존 결과를 돌려줍니다.

공식적으로 새 발행 기능이 제공되더라도 별도 확인·검토·시험 전까지 활성화하지 않습니다.
스마트에디터 HTML/이미지 붙여넣기는 [별도 실제 시험표](naver-paste-test.md)에 남겨 두었으며 호환성을 보증하지 않습니다.
통합 시험은 가짜 게시글 URL을 사용했고 네이버에 실제 글을 게시하지 않았습니다.
