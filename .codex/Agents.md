# 한국어 응답 규칙
## 언어 설정
- 모든 응답은 한국어로 작성합니다.
- 코드 주석도 가능한 한 한국어로 작성합니다.
- 기술 용어는 필요 시 영어와 한국어를 병행 표기합니다 (예: 컨테이너(container)).
- 에러 메시지·로그는 원문 유지, 설명은 한국어로 제공합니다.

## 예외 상황
- 파일명은 영어로 작성.
- 코드(식별자)는 영어로 작성(변수명, 함수명 등).
- 공식 문서/명령어는 원문 유지.
- 사용자가 다른 언어를 명시 요청한 경우에만 예외.

# 작업 프로세스 체크리스트
- 변경 범위 정의: 목적/영향 모듈 명확화.
- 최소 단위 수정: 작은 패치로 나누고 각 단계 기록.
- 기록 항목: 의도/배경, 변경사항 설명, 수정 파일 경로와 요지, 비고(이슈/의존성).
- 문서 동기화: mermaid/README/설정 파일 갱신 여부 확인.
- 로컬 검증: 기본 테스트/스모크 런 수행(가능 시 `pytest`, 샌드박스 환경 제약 고려).
- 기록 반영: `docs/note_working.md`에 3줄 공백 규칙으로 로그 추가.

기록 템플릿 예시:

```
YYYY-MM-DD (작성자)
의도: …
변경: …
수정파일: a/b/c.py, d/e.md …
비고: …
```

# 파일 참조/라인 표기 규칙
- 파일 경로는 클릭 가능한 형태로 표기: `path/to/file.ext`
- 라인 표기: `path/to/file.ext:42` 또는 `path/to/file.ext#L42`
- 범위 표기는 지양하고 단일 라인 기준으로 참조.

# Mermaid/문서 갱신 규칙
- 다이어그램은 영어 라벨을 사용하며, 실제 경로나 모듈명은 하위 줄로 병기.
- 다이어그램 내 주석(mermaid `%%` 코멘트)은 한국어로 작성.
- 엣지(화살표) 주석은 데이터 방향과 의미가 드러나게 구체화.
- 레이아웃은 기본 `LR` 유지, 필요한 경우만 `TB` 등으로 변경.
- 파일 위치: `docs/mermaid/*.mmd` (예: `docs/mermaid/data_flow.mmd`).


# 추가 가이드
- PV 네이밍/스코프는 기존 패턴을 준수(예: `BL:DCM:CRYO:*`).
- 새 파라미터 도입 시 기본값과 유효 범위를 `tools/*.yaml`에 정의하고 코드에서 검증.
- 인터락/안전 관련 변경은 주석과 문서에 근거/가정을 명확히 기재.
- `tools/tuning.yaml`은 `tools/pv_init.yaml`의 `config`/`pvs`를 얕게 병합(overwrite)하여 적용하므로, 변경 시 다이어그램과 문서를 함께 업데이트.


# 코드 작성 규칙(역할/경계)
- sim/core/dcm_cryo_cooler_sim.py: CryoCooler 물리 시뮬레이터 코어
    - 핵심 모델(State/Controls/CryoCoolerSim)과 연속시간 물리 갱신(step) 구현.
    - EPICS/상위 로직 비의존. 외부에서 제어변수만 주입받음.
- sim/logic/commands.py: 운영 명령/상태 enum과 매핑
    - MainCmd/ModeCmd/State 정의, ModeCmd→Sequencer.AutoKind 매핑 제공.
    - 물리/EPICS 비의존. 로직 간 공유 타입의 단일 소스.
- sim/logic/operating.py: 운영 상태 전이/시퀀스 트리거 로직
    - OperatingLogic: Main/Mode 입력 기반 상태 전이 규칙(next_state)과 시퀀서 호출(apply_mode_action).
    - EPICS 비의존. 순수 값→상태/액션 결정에 집중.
- tools/pv_bridge.py: EPICS PV 브리지
    - pyepics로 PV 읽기/쓰기, 시뮬레이터/시퀀서 구동, 운영 로직 호출.
    - CLI 인자 파싱, YAML 초기값/튜닝 적용, 히스토리 파형 게시 등 애플리케이션 계층.