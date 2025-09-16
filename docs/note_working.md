2025-09-16 (Codex)
의도: READY/HIST PV 미연결 시 반복 put로 루프 지연 발생 문제 진단 및 비연결 PV 스킵 처리.
변경: pv_bridge PV 쓰기 헬퍼와 히스토리 게시가 연결 상태 확인 후 put하도록 조정하여 지연 완화 예정.
수정파일: `tools/pv_bridge.py`, `docs/note_working.md`
비고: PV 연결 시 자동으로 재게시되도록 주기적 put 유지.



2025-09-16 (Codex)
-의도: 프리셋/수동 명령이 밸브 독립 제어 규칙을 위반하지 않도록 Sequencer 경계를 재정비.
- 변경: 수동 오버라이드 상태(_ManualOverrides) 도입, 프리셋/수동/STOP/OFF이 직접 밸브를 조작하지 않고 오버라이드와 update(0)로 위임. `update()`를 수동 모드 분기와 규칙 실행 헬퍼로 재구성하고, 각 `rule_*` 함수가 수동 오버라이드를 우선 적용하도록 수정.
- 수정파일: `sim/logic/sequencer.py`, `docs/note_working.md`
- 비고: AUTO 시작 시 오버라이드 초기화(`_on_auto_changed`), HOLD 중에는 기존 상태 유지. `pytest` 실행 결과 테스트 없음(exit code 5).



2025-09-15 (Codex)
의도: PURGE 제어 경로 명확화 및 주석 정리. 자동 시퀀스 중 V21 강제 닫힘 유지, 프리셋(PURGE)에서는 시퀀서 규칙이 개입하지 않음을 문서화.
변경: `rule_v21_purge()` 주석을 실제 경로에 맞게 수정 — PURGE는 `OperatingLogic.plan_action`→브리지(`tools/pv_bridge.py`)→`Sequencer.preset_purge()`로 제어되며, AUTO가 NONE인 상태에서는 `update()`가 조기 반환하여 규칙이 실행되지 않음을 명시. 기능 변경 없음.
수정파일: `sim/logic/sequencer.py`, `docs/note_working.md`
비고: 동작 동등성 유지. 안전 관점에서 자동 시퀀스 중(V21 닫힘) 보장.



2025-09-15 (Codex)
의도: 밸브 제어규칙(Independent Valve Rules) 위반 수정 및 규칙 분리. 각 규칙 함수가 자신의 밸브만 제어하도록 정리.
변경: `rule_v9_dcm_supply()`에서 `V21` 제어 제거(루프 퍼지는 `rule_v21_purge()`에서만 관리). `rule_pump_v10_baseline()`을 `rule_pump_baseline()`과 `rule_v10_mode()` 두 규칙으로 분리하여 밸브/비밸브 구동 분리. `update()` 호출 순서에서 분리된 규칙 적용.
수정파일: `sim/logic/sequencer.py`
비고: 공통 조건/게이팅은 헬퍼로 유지(`_hv_refill_active`, `_hv_refill_gating_ok`, `_sc_refill_active`). 동작 동등성 유지.



2025-09-15 (Codex)
의도: pv_bridge 초기값 하드코딩 제거, pv_init.yaml로 일원화. 브리지는 PV I/O와 외부 로직 호출만 수행하도록 최소화.
변경: 초기 SUBCOOLER(77.3K)·장치 상태(펌프/히터/밸브/흐름/알람/안전)·DCM power 초기 put 제거. 초기값 적용은 `tools/pv_init.yaml`의 `pvs` 섹션만 사용. alarm/safety는 루프 내 로직으로 계산.
수정파일: `tools/pv_bridge.py`
비고: `--init-config` 미지정 시 `tools/pv_init.yaml` 자동 탐색. IOC에 PV가 이미 구성되어 있으면 해당 값을 유지.



2025-09-15 (Codex)
의도: pv_bridge에서 sim.controls 직접 접근 제거(읽기/쓰기 모두), sequencer 전용 경계 준수. 브리지는 오직 PV I/O와 Sequencer/OperatingLogic 호출만 수행.
변경: `Sequencer`에 `preset_ready/preset_purge/aux_off/set_press_sp/apply_manual_commands/snapshot_status` 추가. `tools/pv_bridge.py`는 새 API로 프리셋/보조/수동명령/설정점 처리 및 상태 미러링 수행. 모든 `sim.controls.*` 참조 제거(주석 제외).
수정파일: `sim/logic/sequencer.py`, `tools/pv_bridge.py`
비고: 기능 동등성 유지. READY LED/상태 게시, 히스토리/로그 동작 동일.
2025-09-15 15:20:00 KST

작업 내역
- 시퀀서 규칙(Independent Valve Rules) 기반으로 리팩터링
  - `rule_*` 함수로 밸브별 단일 책임 구현(V9/V11/V21/V15/V20/V17/V19, 펌프/V10, 압력/히터)
  - HV/SC 초기보충 및 재보충 히스테리시스 구현(HV: 39↔41, SC: 49↔51), 목표 90%
  - COOL_DOWN 재보충 시 게이팅 적용(V9=OPEN, V17>0, V20 펄스 1.0s)
  - 업데이트 순서 적용: 베이스라인→루프→벤트→HV펄스→HV/SC리필→퍼지→압력

변경 사항
- `sim/logic/sequencer.py`: 단계(stage) 의존 로직 제거, 규칙/헬퍼/내부 상태 추가
- ACCEPT 기준 반영: READY 조건 충족 시 COOL_DOWN 종료 및 상태 텍스트 유지
- `sim/core/dcm_cryo_cooler_sim.py`: `stop()/off()` 메서드 제거(제어는 Sequencer가 단일 소유)
- READY 판정 위치 이동: `_is_ready()`를 시퀀서로 이동하여 제어/판정 일원화, `sim.step()`에서는 ready 플래그를 갱신하지 않음




2025-09-15 16:10:00 KST
작업 내역
- READY 상태 enum 추가 및 GUI 표시 연동

변경 사항
- `sim/logic/commands.py`: `OperState.READY = 8` 추가
- `DCM_CCV2App/Db/dcm_cryo.db`: `STATE:MAIN` mbbi에 `EIST="READY"` 추가(값 8)
- `tools/pv_bridge.py`: `sim.state.ready==True`이면 `STATE:MAIN`을 READY로 override하여 GUI에 표시
- `ioc/snl/dcm_cryo.stt`: READY(8) → `STATE:TEXT="READY"` 매핑 추가



2025-09-15 16:25:00 KST

작업 내역
- READY LED 추가 및 Boolean PV 게시

변경 사항
- `DCM_CCV2App/Db/dcm_cryo.db`: `BL:DCM:CRYO:READY`(`bi`) 추가
- `tools/pv_bridge.py`: READY 플래그를 `BL:DCM:CRYO:READY`로 게시
- `gui/bob/main.bob`: 좌측 패널에 `ReadyLED` 및 레이블 추가, PV=`$(P)READY`, on색상=녹색

수정파일
- DCM_CCV2App/Db/dcm_cryo.db
- tools/pv_bridge.py
- gui/bob/main.bob

수정파일
- sim/logic/commands.py
- DCM_CCV2App/Db/dcm_cryo.db
- tools/pv_bridge.py
- ioc/snl/dcm_cryo.stt

비고
- BOB 파일에서 READY LED 규칙은 `STATE:MAIN==8` 또는 `STATE:TEXT=="READY"`로 손쉽게 구성 가능(필요 시 후속 패치)

수정파일
- sim/logic/sequencer.py
- sim/core/dcm_cryo_cooler_sim.py

비고
- 물리 갱신(`sim.step`)은 기존대로 브리지 루프에서 호출(이중 호출 방지). 필요 시 후속 이슈로 이동 가능.

변경 사항
- HMI에서 초기 레벨(LT19/LT23)을 7% 등으로 설정한 경우, START 시 자동 시퀀스가 내부 상태와 일치된 레벨로 진행 → V15가 즉시 닫히는 현상 방지

수정파일
- tools/pv_bridge.py: 루프 초기화에서 LT19/LT23를 `_read()`로 동기화하는 코드 추가(초기/설정 적용 후 2회)

비고
- 여전히 비정상 동작 시, MODE/MAIN/레벨 값을 주기적으로 로깅하여 타이밍 이슈를 추가 진단 예정
2025-09-15 (Codex)
의도: OperatingLogic에서 시뮬레이터 직접 조작(sim.controls) 제거, 코드 경계(순수 결정 로직) 준수. 브리지가 해석·적용할 액션 계획(plan_action)으로 분리.
변경: `OperatingLogic.ActionType/Action` 도입 및 `plan_action()` 추가, 기존 `apply_mode_action()`의 sim 조작 제거. `tools/pv_bridge.py`에서 `plan_action()` 결과를 해석하여 시퀀서 호출 및 READY/PURGE 프리셋·AUX OFF 처리.
수정파일: `sim/logic/operating.py`, `tools/pv_bridge.py`
비고: 기능 동등성 유지(READY/PURGE, REFILL_HETER/SBCOL OFF, REFILL_HV 사전효과). mermaid 문서는 후속 동기화 가능.
2025-09-15 (Codex)
의도: READY 플래그 주석 구분(사전/사후 계산 목적 명확화).
변경: `sim/logic/sequencer.py`의 두 주석 문구를 각각 "사전계산(규칙 전, 표시용)"과 "사후계산(규칙 후, 자동 종료 판정)"으로 수정.
수정파일: `sim/logic/sequencer.py`
비고: 기능 변화 없음(설명만 보강).

2025-09-15 (Codex)
의도: COOL_DOWN 모드에서 V10 개도 요구사항 반영(60%). 밸브 독립 규칙 원칙 유지.
변경: `rule_v10_mode()` 로직 수정 — 모드별 개도 설정: COOL_DOWN=0.6, OFF/PURGE=1.0, 기타=0.0.
수정파일: `sim/logic/sequencer.py`
비고: 다른 규칙과의 충돌 없음(V10은 해당 규칙에서만 제어).
