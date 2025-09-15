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
