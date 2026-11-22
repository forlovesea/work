"""Local-first automatic authoring. Server delivery is a separate retryable step."""
import uuid

from .manual import ManualHandoff
from .services import ServiceError
from .storage import utcnow

VERSION = "1.1.0"


def author_locally(services, config, api_key, progress=None):
    progress = progress or (lambda message: None)
    run_id = str(uuid.uuid4())
    state = {"run_id": run_id, "started_at": utcnow(), "mock": config.mock,
             "status": "running", "stage": "글 생성"}
    services.store.put("last_authoring_run", state)

    def stage(message):
        state["stage"] = message
        services.store.put("last_authoring_run", state)
        progress(message)

    try:
        if not config.mock and not api_key:
            raise ServiceError("실제 자동 작성에는 OpenAI API 키가 필요합니다. 설정에 키를 저장하거나 무료 Mock 점검을 사용하세요.")
        stage("글 생성")
        article = services.write_article(config, api_key, config.topic, run_id=run_id)
        state["article_id"] = article["id"]
        image = None
        if config.scheduled_image:
            stage("이미지 생성 · 글에 첨부")
            image = services.generate_image(config, api_key, config.topic)
            article["images"] = [{**image, "id": str(uuid.uuid4()), "caption": config.topic}]
            services.store.save_article(article)
        stage("HTML · Word · ZIP 로컬 저장")
        path = ManualHandoff(services).prepare(config, article)
        state.update(status="completed", stage="로컬 작성 완료 · 서버 전송은 별도", path=str(path), finished_at=utcnow())
        services.store.put("last_authoring_run", state)
        services.store.log("INFO", "자동 작성 완료: 글·출력 ZIP 로컬 저장. 서버 전송은 별도입니다.")
        return {"article": article, "image": image, "path": str(path), "run": state}
    except Exception:
        state.update(status="failed", finished_at=utcnow())
        services.store.put("last_authoring_run", state)
        services.store.log("ERROR", "자동 작성 실패 단계: " + state["stage"] + ". 이미 저장된 초안은 글쓰기 이력에서 확인하세요.")
        raise
