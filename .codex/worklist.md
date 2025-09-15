# 3계층 구조 전환 작업 리스트

목표: 물리 시뮬레이터(Plant)·운전 시퀀서(Sequencer)·브리지/오퍼레이팅(EPICS I/O + 상태전이)로 역할을 분리.

## 완료
- Sequencer 신규 도입 (`sim/logic/sequencer.py`)
  - `AutoKind`, `Sequencer(update/start_*/stop/off/hold/resume)` 구현
  - 기존 시뮬레이터의 `_update_auto`/`auto_*` 로직을 Sequencer로 이전
  - LT19 자동 보충 히스테리시스도 Sequencer에서 수행

- Operating → Sequencer 위임 (`sim/logic/operating.py`)
  - `apply_mode_action(seq, ...)`로 시그니처 변경
  - START(모드별) → `seq.start_*()` 호출
  - STOP/HOLD/RESUME/OFF → `seq.stop/hold/resume/off`
  - READY/PURGE는 직접 `seq.sim.controls` 셋업

- PV Bridge 갱신 (`tools/pv_bridge.py`)
  - `from sim.logic.sequencer import Sequencer, AutoKind`
  - `self.seq = Sequencer(self.sim)` 생성
  - 수동 게이팅: `self.seq.auto != AutoKind.NONE`
  - 명령 처리: `apply_mode_action(self.seq, ...)`로 위임
  - 루프에서 `self.seq.update(self.dt)` 후 `self.sim.step()` 실행
  - 이벤트/트레이스 로그에 `self.seq.auto/stage` 사용

## 추가 완료(Plant 최소화)
- Plant 자동 개입 비활성화 (`sim/core/dcm_cryo_cooler_sim.py`)
  - `step()`에서 `_update_auto()` 호출 제거
  - `_update_levels()`의 LT19 자동 보충 및 LT23<5% 강제 stop 제거
  - `__main__` 데모를 Sequencer 기반으로 전환

## 보류/다음 단계 (선택)
- Plant에서 레거시 자동 관련 정의 완전 제거(호환성 위험 시 유지)
  - `AutoKind`, `auto_*`, `_update_auto`, `paused/stage`/타이머 필드 삭제 정리

- 문서/다이어그램 보강
  - `docs/mermaid/pv_bridge_flow.mmd`에 Sequencer 참여자 추가 반영(선택)

## 검증 안내
- 브리지 실행 시 동작 확인 포인트
  - AUTO/Stage 이벤트 로그가 Sequencer 기준으로 출력되는지
  - START+MODE(COOL_DOWN 등) 시 `controls`가 단계적으로 변하는지
  - STOP/OFF/HOLD/RESUME 명령 처리 후 수동 조작 허용/차단이 기대대로 되는지
  - HIST 파형/프로세스 PV 게시는 종전과 동일한지

## 롤백/안전장치
- Plant의 레거시 auto API는 여전히 존재(호환성); 브리지는 Sequencer만 사용
- 문제가 있을 경우 `tools/pv_bridge.py`에서 `self.seq.update()` 호출을 임시 비활성화하여 종전 Plant 자동 로직 경로로 테스트 가능(권장하진 않음)
