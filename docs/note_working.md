2025-09-11 18:02:05 KST

작업 내역
- 변수명/키 통일(기준: `sim/core/dcm_cryo_cooler_sim.py`)
  - `tools/pv_bridge.py`: PT1/PT3/FT18/HIST PV 상수화 및 사용, 헤더 주석에 CMD/Mode 명세 추가
  - `tools/pv_init.yaml`: `q_dcm`로 완전 통일(`qload` 제거), 불필요/레거시 키 삭제
  - `tools/operating.yaml`: 키 설명 주석을 `OperatingLogic` 기준으로 정리
  - `sim/logic/operating.py`: 주석 갱신(CMD/Mode 정의와 역할 분리 명시)

변경 사항
- 코드 가독성 향상: 인라인 문자열 PV 이름을 상수로 치환(일관성 확보)
- 설정 파일 가독성 향상: 사용 키/비사용 키 구분 및 주석 정리

수정파일
- tools/pv_bridge.py
- tools/pv_init.yaml
- tools/operating.yaml
- sim/logic/operating.py

비고
- 기능 변경 없음(명세/주석/상수화 중심). 기존 시나리오/GUI 동작에는 영향 없음.



2025-09-12 21:18:00 KST

작업 내역
- STOP/OFF 명령 직후 시뮬레이터가 설정한 V10/V17/V20 값이 다음 루프에서 수동 PV 매핑에 의해 0으로 덮어써지는 문제 수정

변경 사항
- `pv_bridge`의 STOP/OFF 차단 로직 제거하고, 대신 STOP/OFF 직후 현재 시뮬레이터 상태를 CMD PV로 동기화하여 즉시 수동모드로 전환되도록 변경

수정파일
- tools/pv_bridge.py: `_apply_manual_actuators_if_allowed()` STOP/OFF 차단 제거, `_sync_manual_cmd_pvs_from_sim()` 추가 및 STOP/OFF 시 호출

비고
- 자동 시퀀스 진행 중(`auto != NONE`)에도 기존대로 수동 조작 차단 유지. START/READY 등 정상 운전 상태에서만 수동 명령 반영.
2025-09-12 21:05:00 KST

작업 내역
- 메인 명령에서 ESTOP(EMERGENCY_STOP) 명칭을 OFF로 변경
- STOP/OFF 기능 차별화 구현:
  - STOP: 기본 상태로 복귀(모든 밸브 CLOSE, V10 100% OPEN, 펌프 OFF, 압력제어 OFF, Ready 꺼짐), 자동절차 즉시 중지
  - OFF: STOP과 동일 + 루프 벤트 V17, HV 벤트 V20을 OPEN하여 과압 방지 상태로 안전 워밍업

변경 사항
- EPICS DB의 CMD:MAIN 맵에서 5번 항목을 EMERGENCY_STOP→OFF로 변경
- 브리지(`pv_bridge`)의 CMD 딕셔너리 및 설명 주석 업데이트, HOLD 래치 해제 집합에 OFF 반영
- 운영 로직(`operating`)에서 EMERGENCY_STOP 분기를 OFF로 대체하고, OFF 명령 시 `sim.off()` 호출하도록 처리
- 시뮬레이터 STOP 동작 강화: 모든 밸브 CLOSE(V9/V11/V15/V19/V21=Close, V17/V20=0), 단 V10=100% 유지
- 참고 문서/도표 일부(Reference/mermaid)에서 명칭 반영

수정파일
- DCM_CCV2App/Db/dcm_cryo.db: CMD:MAIN의 FVST 문자열 변경
- tools/pv_bridge.py: 명령 정의/주석 및 HOLD 해제 집합 수정(OFF 반영)
- sim/logic/operating.py: MainCmd 열거형/전이/액션 업데이트(OFF 처리, `sim.off()` 호출)
- sim/core/dcm_cryo_cooler_sim.py: `stop()`에서 밸브 일괄 CLOSE 로직 명확화
- docs/Reference/Reference_Guide.md: CMD:MAIN 표/DB 예시 업데이트
- docs/mermaid/state_machine.mmd: EMERGENCY_STOP → OFF 전이 수정

비고
- SAFE_SHUTDOWN 상태는 인터락/알람 경로에서만 사용(직접 명령 삭제). 추가 연결이 필요하면 추후 별도 이슈로 연계 예정.
2025-09-12 14:34:20 KST

작업 내역
- LT19/LT23 초기 레벨을 `pv_init.yaml`에서 손쉽게 설정 가능하도록 `config` 키 추가
- `lt19_init_pct`, `lt23_init_pct` 값을 지정하면 브리지가 시뮬레이터 상태와 PV를 동시에 초기화

변경 사항
- `pvs:`로 직접 PV를 지정하지 않아도 레벨 초기값을 구성에서 제어 가능(두 방식 병행 사용 가능)

수정파일
- tools/pv_bridge.py: `_apply_init_from_yaml()`에 `lt19_init_pct`/`lt23_init_pct` 처리 추가
- tools/pv_init.yaml: 해당 키 주석/예시 추가

비고
- 초기 동기화 경로: (1) IOC PV→sim.seed, (2) YAML 적용, (3) PV→sim 재동기화, (4) 루프 중 sim→PV 주기 publish
2025-09-12 14:22:20 KST

작업 내역
- LT23(히터 베셀) 소비가 압력제어/전력 변화에 둔감한 문제에 대한 조정 파라미터 추가 및 레벨 동역학 보강
- 시뮬레이터에 HV 소비 항 추가(기본/전력/히터동작/벤트 기여) 및 YAML로 튜닝 가능하게 연결

변경 사항
- 압력제어 on 시 히터 동작(u._heater_u)에 비례한 LT23 소비가 발생(튜닝값으로 조절 가능)
- 전력 증가(DCM POWER↑) 또는 V20 개방 시 LT23 감소율 증가(튜닝값에 비례)

수정파일
- sim/core/dcm_cryo_cooler_sim.py: HV 소비 항목 속성/기본값 추가 및 `_update_levels`에 소비식 반영
- tools/pv_bridge.py: `_apply_init_from_yaml()`에서 lt23_* 파라미터 읽어 시뮬레이터에 주입
- tools/pv_init.yaml: lt23_* 설정 키와 주석 가이드 추가

비고
- 기본값은 보수적으로 0(비활성)로 두었고, 현장 요구에 맞게 YAML에서 값을 올려 사용하면 됩니다.
2025-09-12 14:08:30 KST

작업 내역
- SubTank(LT19) 소비량이 DCM Power 변화(100W↔1000W)에 둔감한 문제 조정 가능하도록 파라미터 외부화
- `pv_bridge`에서 YAML(config)로 다음 항목을 받아 시뮬레이터에 주입:
  - `lt19_base_cons_lps`: 기본 소비량 [L/s]
  - `lt19_power_cons_lps_perW`: 전력당 추가 소비 [(L/s)/W]
  - `lt19_vent_gamma_lps_perLpm`: 벤트 경로 손실 계수 [(L/s)/(L/min)]
- `tools/pv_init.yaml`에 주석 가이드 추가(강한 전력 민감도 예시 포함)

변경 사항
- 구성만으로 소비량 민감도를 손쉽게 키워 100W와 1000W의 LT19 소모 차이를 크게 만들 수 있음

수정파일
- tools/pv_bridge.py: `_apply_init_from_yaml()`에 lt19_* 파라미터 처리 추가
- tools/pv_init.yaml: lt19_* 파라미터 사용 예시/주석 추가

비고
- 기본 모델 상수는 유지되며, 필요 시 YAML에서 상수 덮어쓰기로 현장 튜닝 가능
2025-09-12 13:50:10 KST

작업 내역
- PV 갱신 일관성 보완: 루프 초기화 시 `BL:DCM:CRYO:DCM:POWER`에 내부 `q_dcm` 초기값을 반영하여 HMI 표시값과 동기화

변경 사항
- 브리지 시작 후 `caget BL:DCM:CRYO:DCM:POWER`가 CLI `--q_dcm`와 일치

수정파일
- tools/pv_bridge.py: 루프 초기화에서 `pv_dcm_power` 초기 write 추가

비고
- 이후 루프에서는 해당 PV를 입력으로 읽어 내부 열부하를 갱신합니다.
2025-09-12 13:38:20 KST

작업 내역
- LT19/LT23 PV 값이 갱신되지 않는 문제 수정: 시뮬레이터 상태값을 매 루프마다 PV(`BL:DCM:CRYO:LEVEL:LT19`, `LT23`)로 publish

변경 사항
- `caget`로 확인 시 LT19/LT23 값이 로그와 동일하게 증가/변화

수정파일
- tools/pv_bridge.py: `sim.step()` 이후 `pv_lt19/pv_lt23`에 `_write_float()` 추가

비고
- 초기 동기화는 기존대로 PV→시뮬레이터 반영, 이후 루프에서는 시뮬레이터→PV로 지속 업데이트
2025-09-12 12:15:45 KST

작업 내역
- 타이밍 이슈 추적을 위해 `pv_bridge`에 주기 로깅 옵션 추가(`--log-interval`)
- 로그 항목: 시간, CMD(Main), MODE(raw), effMODE(latched), STATE, V15/V19 상태, LT23/LT19

변경 사항
- 명령/모드/레벨 변화가 시간축에서 어떻게 상호작용하는지 CLI에서 직접 관찰 가능

수정파일
- tools/pv_bridge.py: `--log-interval` 파라미터 추가 및 루프 내 주기 출력 구현

비고
- 사용 예: `python -m tools.pv_bridge --verbose --log-interval 0.5`
2025-09-12 12:03:10 KST

작업 내역
- START 직후 V19/V15가 꺼진 상태로 유지되는 문제의 원인 후보(레벨 초기값 불일치) 대응
- 브리지 초기화 시 LT19/LT23를 IOC PV에서 읽어 시뮬레이터 상태에 동기화하고, `pv_init.yaml` 적용 후에도 재동기화

변경 사항
- HMI에서 초기 레벨(LT19/LT23)을 7% 등으로 설정한 경우, START 시 자동 시퀀스가 내부 상태와 일치된 레벨로 진행 → V15가 즉시 닫히는 현상 방지

수정파일
- tools/pv_bridge.py: 루프 초기화에서 LT19/LT23를 `_read()`로 동기화하는 코드 추가(초기/설정 적용 후 2회)

비고
- 여전히 비정상 동작 시, MODE/MAIN/레벨 값을 주기적으로 로깅하여 타이밍 이슈를 추가 진단 예정
2025-09-12 11:45:30 KST

작업 내역
- 아키텍처 정리: `pv_bridge`는 순수 PV 중계로 유지하고, 시퀀스 트리거/진행은 `sim/logic/operating.py`에서만 수행
- 모드 변경 시에는 `OperatingLogic.set_mode()`만 호출(행동 없음), START/STOP 등 MainCmd 변화 시에만 `apply_mode_action()` 호출

변경 사항
- Refill-HV 모드 선택만으로 밸브가 깜빡이는 현상 방지(START 없이 동작 금지)
- START 시 래칭된 모드로 시퀀스 안정 트리거(앞서 추가한 모드 래치 `_last_nonzero_mode`와 함께 동작)

수정파일
- tools/pv_bridge.py: 모드/명령 변화 감지 분리, `set_mode()` 호출 추가, `cmd_changed`에서만 액션 실행

비고
- HMI가 START 시 MODE를 0으로 되돌려도, 브리지는 마지막 유효 모드를 유지해 시퀀스가 정상 시작됩니다.
2025-09-12 11:32:20 KST

작업 내역
- START 시점에 HMI가 MODE를 `NONE(0)`으로 되돌려 자동 시퀀스 트리거가 누락될 수 있는 타이밍 이슈 보완
- 브리지에서 최근 유효 모드(latched)를 기억하여, START 펄스 처리 시 `mode_val=0`이면 마지막 비-제로 모드를 사용

변경 사항
- "Refill HV ON" 선택 후 START 시, `auto_refill_hv()`가 안정적으로 시작되어 V15가 즉시 OPEN 상태 유지
- 상태 전이(`next_state`) 계산에도 동일한 유효 모드 적용으로 일관성 확보

수정파일
- tools/pv_bridge.py: `_last_nonzero_mode` 추가 및 `apply_mode_action`/`next_state` 호출에 `eff_mode_val` 적용

비고
- HMI/IOC 환경에 따라 MODE가 START 직후 초기화되는 경우가 있어 래칭이 필요합니다.
2025-09-12 11:17:40 KST

작업 내역
- "Heater Vessel Refill ON" 모드 실행 시 즉시 V15(히터 베셀 주입 밸브)가 열리도록 보장
- `sim/logic/operating.py`의 `apply_mode_action`에서 `REFILL_HETER_ON` 처리 시, 자동 시퀀스 시작 전 `V15=True`, `press_ctrl_on=False`를 선반영

변경 사항
- UI에서 모드 선택 후 START 시, V15가 즉시 OPEN으로 반영(깜빡임 없이 명확)
- 자동 시퀀스(`auto_refill_hv`) 동작은 기존과 동일하며, V19는 LT19 히스테리시스 로직에 의해 필요 시에만 동작

수정파일
- sim/logic/operating.py: REFILL_HETER_ON 분기에서 V15/press_ctrl_on 선반영 추가

비고
- 실제 IOC/HMI에서 동작 확인 권장. 추가로 verbose 로깅(모드/명령/밸브 상태) 출력이 필요하면 알려주세요.
2025-09-12 11:05:00 KST

작업 내역
- `tools/pv_bridge.py` 루프에서 `flow_v17/flow_v10` 변수를 정의하기 전에 히스토리(`hist_flow_v17`, `hist_flow_v10`)에 추가하여 `UnboundLocalError`가 발생하던 문제 수정
- 파생 유량 값 계산(`v17_pos`, `flow_v17`, `flow_v10`)을 히스토리 업데이트 전에 선계산하도록 순서 조정

변경 사항
- 런타임 예외 제거: `UnboundLocalError: local variable 'flow_v17' referenced before assignment` 해소
- 기능/동작 변화 없음(계산식과 출력은 동일, 순서만 조정)

수정파일
- tools/pv_bridge.py: 히스토리 갱신 이전에 유량 계산 코드 이동

비고
- `timeout 2s python -m tools.pv_bridge --verbose`로 단기 실행 점검(비상 종료 시 출력 없음). 실제 IOC 연결 환경에서 정상 동작 예상.
2025-09-11 17:46:16 KST

작업 내역
- CMD 체계 역할 분리 반영 (main.bob 기준): Select Mode(`$(P)CMD:MODE`)로 시퀀스 선택, System Control(`$(P)CMD:MAIN`)으로 실행/정지 제어
- `CMD:MAIN`에서 `WARMUP` 명령 제거(모드는 `CMD:MODE=Warm-up`으로 선택 후 `CMD:MAIN=START`로 실행)
- 브리지/로직의 명령 맵과 문서 일치화

변경 사항
- DCM_CCV2App/Db/dcm_cryo.db: `CMD:MAIN` 레코드에서 `SVST WARMUP` 제거
- sim/logic/operating.py: MainCmd Enum 및 주석에서 `WARMUP` 제거, 분리된 역할 설명 정합화
- tools/pv_bridge.py: `CMD` 딕셔너리에서 `WARMUP` 항목 제거 (모드+스타트 조합으로 Warm-up 실행)
- docs/Reference/Reference_Guide.md: `CMD:MAIN` 표기 수정(0=NONE…6=RESET), DB 예시에서 WARMUP 라인 제거 및 주석 추가

수정파일
- DCM_CCV2App/Db/dcm_cryo.db
- sim/logic/operating.py
- tools/pv_bridge.py
- docs/Reference/Reference_Guide.md

비고
- GUI(`gui/bob/main.bob`)는 PV 라벨을 DB에서 읽으므로 별도 수정 없이 일치합니다.



2025-09-11 17:42:50 KST

작업 내역
- `.codex/work-rules.md`(작업 규칙) 확인 및 준수 선언
- 한국어 응답 규칙 요약: 모든 답변은 한국어, 코드와 파일명은 영어(식별자/파일명), 기술 용어는 한·영 병기, 에러/로그는 원문 유지+한국어 설명
- 프롬프트 작업규칙 준수: 모든 작업을 `docs/note_working.md`에 기록, 새 항목 앞 3줄 공백으로 구분, 필수 섹션(작업/변경/수정파일/비고) 포함

변경 사항
- 코드/구성 변경 없음(프로세스 준수 확약만 추가)

수정파일
- docs/note_working.md: 본 항목 추가

비고
- 이후 모든 응답은 한국어로 제공하며, 기술 용어는 필요 시 병기합니다.



2025-09-10 10:51:13 KST

작업 내역
- 한국어 응답 규칙 문서(.codex/korean-language.md) 확인 및 적용 동의
- docs 디렉터리 상태 점검 (기존 *.mmd, README.md 확인)
- 초기 작업 로그 파일(note_working.md) 생성 및 기록 추가

비고
- 이후 변경 사항 발생 시 본 파일 상단에 날짜/시간을 먼저 기록하고 작업 내용을 누적합니다.




2025-09-10 10:56:58 KST

작업 내역
- data_flow.mmd 다이어그램 최신화
  - IOC에 st.cmd, db, HIST 파트 추가
  - Bridge와 optional operating/interlock 논리의 관계를 명시 (dash link)
  - DB↔Bridge 방향성 및 신호 종류(명령/설정/측정/알람/히스토리) 주석 추가
  - GUI와 HIST 연계 표시

변경 사항
- IOC: iocBoot/iocDCM_CCV2/st.cmd, db/dcm_cryo.db, BL:DCM:CRYO:HIST:* 노드 추가.
- Bridge: sim.logic.operating, sim.logic.interlock를 옵션으로 표기하고 점선 화살표로 의존성 명시.
- 방향/주석: DB→Bridge(명령/설정/입력), Bridge→DB(측정/상태/알람), Bridge→HIST(히스토리) 주석 추가.
- GUI: gui/bob/main.bob가 DB 및 HIST와 연계됨을 표기.
- Config: pv_init.yaml, operating.yaml, interlock.yaml이 Bridge로 유입됨을 명확화.
- 부트 경로: st.cmd가 DB 로딩을 트리거하는 흐름 추가.

비고
- operating/state_machine.mmd와의 연계는 별도 문서로 유지
2025-09-10 11:13:05 KST

작업 내역
- data_flow.mmd 렌더링 오류 수정(광범위 호환성 개선)
  - 비ASCII 화살표/특수문자 코멘트 정리
  - 점선 링크(dotted) 라벨 제거, 일반 링크로 단순화
  - 비표준 링크 길이(----)를 표준(---)으로 교체

비고
- Mermaid 구버전 렌더러에서도 정상 동작 확인을 목표로 단순화함
2025-09-10 11:14:58 KST

작업 내역
- data_flow.mmd HIST 노드 라벨 수정
  - `HIST[[...]]` → `HIST["..."]`로 변경하여 특수문자(*) 처리 및 파싱 오류 방지

비고
- 필요 시 `\n` 줄바꿈으로 라벨 가독성 향상 가능
2025-09-10 11:18:30 KST

작업 내역
- data_flow.mmd 엣지 라벨 단순화로 파싱 오류 방지
  - DB→BRIDGE: `"commands/setpoints/inputs"`로 축약
  - BRIDGE→DB: `"measurements/status/alarms"`로 축약

비고
- Mermaid 렌더러별 라벨 파서 차이를 회피하기 위한 보수적 변경
2025-09-10 11:21:30 KST

작업 내역
- data_flow.mmd 전면 단순화로 파싱 오류 해소
  - 모든 엣지 라벨 제거
  - 비ASCII 문자(↔, →) 제거
  - HIST 노드 라벨을 `HIST arrays`로 축약
  - dotted edge(`-.->`)를 일반 링크(`---`)로 통일

비고
- 필요 시 별도 주석/README에 상세 라벨 설명을 기재 예정



2025-09-10 13:56:54 KST

작업 내역
- 밸브 상태에 따른 T5/PT1 게이팅 로직 추가
  - V9 open일 때만 서브쿨러 LN2가 DCM으로 흐르고 T5/PT1 정상 반영
  - V9 close & V21 open 시 대기 개방 상태로 간주: T5=대기온도(tamb), PT1=대기압(1.0)

변경 사항
- 측정치 산출 및 기록 시 밸브 상태 검사 후 값을 보정
- 히스토리(waveform)에도 보정값 반영되도록 적용

수정파일
- tools/pv_bridge.py: 루프 내 T5/PT1 산출 및 기록 로직 보정

비고
- V9 close & V21 close (격리) 시나리오는 기존 모델 값 유지(요청 시 조정 가능)



2025-09-10 13:59:51 KST

작업 내역
- pv_bridge의 조건/게이팅 로직을 operating 로직으로 위임
  - sim/logic/operating.py에 `derive_measurements()` 추가 (T5/PT1 파생)
  - pv_bridge는 밸브 상태와 모델값만 전달하고 결과만 반영하도록 리팩토링

변경 사항
- 아키텍처 분리: 브리지(중계) ↔ 운전/조건 로직 분리 강화

수정파일
- sim/logic/operating.py: `derive_measurements` 구현
- tools/pv_bridge.py: 유효 측정치 계산을 OperatingLogic에 위임

비고
- operating.yaml로도 확장 가능(추후 파라미터화 여지)






2025-09-10 15:28:15 KST

작업 내역
- pv_bridge.py 불필요 항목 정리(중계 목적에 맞춘 슬림화)
  - CLI 옵션에서 init-seconds/precool-band 제거
  - PVBridge 생성자에서 init_seconds/band 제거
  - 내부 전이 보조필드(cmd_last, t_init_left) 삭제
  - _maybe_transition 메서드 완전 제거(주석 형태 잔여 제거)
  - pv_init.yaml 적용 시 init_seconds/precool_band 무시 처리(OperatingLogic 관리)

변경 사항
- 브리지 내 상태 전이/밴드 관련 잔존 코드 제거로 혼동 요소 축소

수정파일
- tools/pv_bridge.py: 파라미터/필드/메서드 제거 및 호출부 수정

비고
- 운영/상태 로직은 sim/logic/operating.py에서 일괄 관리

주요 변경
  sim/logic/operating.py
    derive_measurements(v9_open, v21_open, t5_model, pt1_base, tamb): T5/PT1 유효값 산출
    controller_target(state, STATE, tsp, tamb): OFF/SAFE/WARMUP 시 tamb, 그 외 tsp
    derive_pressures(tch, tamb): PT1/PT3 기저 압력 파생
    comp_status(state, STATE): 콤프레서 RUNNING/텍스트
    device_actuators(pump_cmd, heat_cmd, pump_freq_on/off, heater_power_on/off): 펌프/히터 출력
    valve_flows(v17_cmd, v10_cmd): V17 개도/유량, V10 바이패스 유량
  tools/pv_bridge.py
    내부 상태 전이/유효 TSP/압력/밸브/펌프·히터 로직 제거
    루프에서 OperatingLogic 메서드 호출로 모든 파생값 계산
    OperatingLogic은 tools/operating.yaml 유무와 관계없이 항상 기본 인스턴스로 활성화
    V9/V21 조건에 따른 T5/PT1 게이팅은 OperatingLogic의 derive_measurements 사용

동작 확인 포인트
  상태 전이: BL:DCM:CRYO:CMD:MAIN 변경 → STATE:MAIN, STATE:TEXT 갱신
  TSP 적용: controller_target로 유효 TSP 산출 후 모델 스텝
  T5/PT1: V9=1 → 모델값 반영 / V9=0 & V21=1 → T5≈tamb, PT1≈1.0
  압력: derive_pressures 기반 PT1/PT3 갱신
  밸브: V17:CMD→ VALVE:V17(개도), FLOW:V17; V10:CMD→ FLOW:V10
  펌프/히터: CMD에 따라 RUNNING, FREQ/POWER 산출

참고 파일
  sim/logic/operating.py:20 — OperatingLogic 및 확장 메서드
  tools/pv_bridge.py:398 — controller_target 사용
  tools/pv_bridge.py:421 — derive_pressures 사용
  tools/pv_bridge.py:460 — comp_status 사용
  tools/pv_bridge.py:479 — valve_flows 사용
  tools/pv_bridge.py:487 — device_actuators 사용




2025-09-10 14:03:10 KST

작업 내역
- pv_bridge를 ‘중계’에 집중하도록 재작성 (로직 위임 강화)
  - 상태 전이/컨트롤러 목표/압력/밸브 유량/펌프·히터 출력을 OperatingLogic으로 이동
  - 운영 로직은 operating.yaml 유무와 관계없이 기본 인스턴스를 항상 사용

변경 사항
- sim/logic/operating.py에 보조 메서드 추가: controller_target, derive_pressures, comp_status, device_actuators, valve_flows
- tools/pv_bridge.py 루프에서 위 메서드 호출로 모든 파생값 계산

수정파일
- sim/logic/operating.py (메서드 추가)
- tools/pv_bridge.py (내부 로직 제거 및 위임)

비고
- 브리지는 EPICS I/O와 모델 스텝, 히스토리 퍼블리시만 수행
2025-09-11 18:34:20 KST

작업 내역
- TEMP:COLDHEAD 제거 및 T5로 일원화
  - DB: `BL:DCM:CRYO:TEMP:COLDHEAD` 및 `HIST:TEMP:COLDHEAD` 레코드 삭제
  - GUI: synoptic/main/alarm_config에서 COLDHEAD 참조를 T5로 대체
  - 문서/테스트: COLDHEAD 언급/검증을 T5로 치환
- 히스토리 PV 전역 상수화
  - `PV_HIST_TIME`, `PV_HIST_T5`, `PV_HIST_T6`, `PV_HIST_PT1`, `PV_HIST_PT3`를 모듈 상단에 선언하고 전역 사용
- q_dcm 통일 및 레거시 제거
  - CLI: `--q_dcm`로 통일(`--qload` 제거)
  - YAML: `tools/pv_init.yaml`에서 `qload` 및 레거시 키/주석 제거
  - 스크립트: `tools/run_bridge.sh` 갱신

변경 사항
- DCM_CCV2App/Db/dcm_cryo.db: TEMP:COLDHEAD 계열 레코드 삭제
- tools/pv_bridge.py: COLDHEAD 관련 코드/히스토리 제거, q_dcm 적용, HIST PV 상수화
- gui/bob/*.bob: COLDHEAD → T5로 PV 교체
- docs/Reference_*/device_overview: COLDHEAD 제거 및 설명 정리
- tests/*: COLDHEAD 검증을 T5로 변경
- tools/pv_init.yaml, tools/run_bridge.sh: q_dcm 통일

수정파일
- DCM_CCV2App/Db/dcm_cryo.db
- tools/pv_bridge.py
- tools/pv_init.yaml, tools/run_bridge.sh
- gui/bob/synoptic.bob, gui/bob/main.bob, gui/bob/alarm_config.bob
- docs/Reference/Reference_Guide.md, docs/device_overview.md, docs/mermaid/pv_map.mmd
- tests/scenarios/*.yaml, tests/tools/runner.py

비고
- 기능적 변화는 없음(표현/명칭 정리). GUI와 테스트는 T5 기준으로 동작.
2025-09-11 18:55:16 KST

작업 내역
- `sim/logic/operating.py`를 MainCmd/ModeCmd 중심으로 최소화하여 재작성
  - 유지: `MainCmd`, `ModeCmd`, `OperatingLogic.from_yaml`, `set_mode`, `next_state`(최소 전이 규칙)
  - 제거: 사용되지 않는 파생/보조 메서드(derive_*, comp_status, device_actuators, valve_flows 등)
  - 목적: 불필요 코드 제거로 가독성 및 책임 분리 명확화 (시퀀스/물리는 `sim/core`, EPICS I/O는 `tools/pv_bridge.py`)

변경 사항
- sim/logic/operating.py: 파일 전면 간소화 후 최소 전이 파라미터(`init_seconds`,`precool_band`)와
  START/INIT→PRECOOL→RUN, WARMUP→OFF 전이 규칙 정의

수정파일
- sim/logic/operating.py
- tools/pv_bridge.py (상태 전이/명령 해석을 OperatingLogic에 위임)

비고
- pv_bridge 루프에서 `apply_mode_action`, `next_state`를 호출하여 운영 로직에 위임하도록 조정함.
2025-09-11 19:44:04 KST

작업 내역
- PT3 압력 설정값 변경 기능 추가
  - DB: `BL:DCM:CRYO:PRESS:PT3:SP`(`ao`) 레코드 추가 (0–5 bar)
  - 브리지: `PV_PT3_SP` 추가, 루프에서 해당 PV를 읽어 `sim.controls.press_sp_bar`에 반영
  - 초기값: `tools/pv_init.yaml`에 `PRESS:PT3:SP: 2.0` 추가
  - 문서: Reference PV 표에 `PRESS:PT3:SP` 추가

변경 사항
- 런타임에서 PT3 목표 압력을 PV로 제어 가능. 히터 제어는 기존과 같이 `HEATER:CMD`(press_ctrl_on)로 활성/비활성

수정파일
- DCM_CCV2App/Db/dcm_cryo.db
- tools/pv_bridge.py
- tools/pv_init.yaml
- docs/Reference/Reference_Guide.md

비고
- GUI 바인딩은 추후 필요 시 `PRESS:PT3:SP` 입력 위젯을 추가하면 됩니다.
2025-09-11 20:45:00 KST

작업 내역
- 레벨 동역학 파라미터 YAML 화(튜닝 가능)
  - sim/core/dcm_cryo_cooler_sim.py: `fill_Lps_v19`(LT19 보충 유량 [L/s]), `refill_rate_pctps`/`drain_rate_pctps`(LT23 [%/s]) 인스턴스 변수 추가
  - tools/pv_bridge.py: `tools/pv_init.yaml:config`에서 `lt19_fill_lps`, `lt23_refill_rate_pctps`, `lt23_drain_rate_pctps`를 읽어 시뮬레이터에 반영
  - tools/pv_init.yaml: 키 주석 추가(기본값/단위 명시)

변경 사항
- YAML로 보충/배출 속도 조정 가능 (재시작 또는 init-config 재적용 시 반영)

수정파일
- sim/core/dcm_cryo_cooler_sim.py
- tools/pv_bridge.py
- tools/pv_init.yaml

비고
- 현재 기본값은 테스트 가속을 위해 LT23 보충 10/60 [%/s], 배출 1/60 [%/s]로 설정되어 있음. 실환경에 맞게 YAML로 조정하세요.
2025-09-12 10:05:00 KST

작업 내역
- SUBCOOLER 충전 모드 추가 및 모드 체계 확장
  - `ModeCmd`: REFILL_HETER_ON/OFF, REFILL_SBCOL_ON/OFF 추가(값 5..8)
  - 서브쿨러 자동 보충 시퀀스 구현(`auto_refill_subcooler`)
  - 브리지 설명 주석의 CMD:MODE 매핑 갱신
  - IOC DB의 CMD:MODE 선택지 확장 및 라벨 정합화

변경 사항
- 운전 모드 선택 범위 확장(Refill을 HV/서브쿨러로 분리)
- START + MODE 동작:
  - `Refill HV ON` → `sim.auto_refill_hv()` 실행
  - `Refill SUB ON` → `sim.auto_refill_subcooler()` 실행
- OFF 계열 모드 선택 시 해당 경로 밸브 닫힘(V15/V20 또는 V19) 및 자동 시퀀스 종료

수정파일
- sim/logic/operating.py: `ModeCmd` 확장 및 `apply_mode_action` 분기 추가
- sim/core/dcm_cryo_cooler_sim.py: `AutoKind.REFILL_SUB` 및 `auto_refill_subcooler` 구현
- DCM_CCV2App/Db/dcm_cryo.db: `CMD:MODE` 라벨 확장(5..8)
- tools/pv_bridge.py: 헤더 주석의 CMD:MODE 매핑 갱신

비고
- GUI는 `mbbo` 라벨을 사용하므로 DB 갱신으로 자동 반영
- 기존 `Refill ON/OFF`는 `Refill HV ON/OFF`로 명확화됨



2025-09-12 10:18:00 KST

작업 내역
- IOC가 실제 로드하는 DB 경로 수정 반영(`db/dcm_cryo.db`도 동일 변경 적용)
- `CMD:MAIN`에서 WARMUP 항목 제거(역할 분리 원칙 유지)
- `CMD:MODE`에 7/8 선택지 필드명 오류(FVST/SXST 중복)를 정정하여 EPICS Illegal choice 오류 해결

변경 사항
- `db/dcm_cryo.db`에서 `CMD:MODE`를 0..8까지 정상 정의(ZRST..EIST)
- GUI/IOC에서 7,8 선택 시 오류 로그 미발생 확인 기대

수정파일
- db/dcm_cryo.db: CMD:MAIN에서 WARMUP 제거, CMD:MODE 라벨/필드명 정정 및 확장

비고
- `iocBoot/iocDCM_CCV2/st.cmd`가 `${TOP}/db/dcm_cryo.db`를 로드하므로 해당 파일을 기준으로 유지합니다.



2025-09-12 10:32:00 KST

작업 내역
- HOLD/STOP 동작 명확화 및 구현
  - HOLD: 자동 시퀀스를 "일시 정지"(paused)하여 stage/타이머 보존, 수동조작 불가
  - RESUME: HOLD 해제 후 기존 시퀀스 계속 진행
  - STOP: 자동 시퀀스 완전 종료(auto=None) 및 수동조작 허용(브리지 규칙과 일관)
  - 시뮬레이터에 `paused` 플래그 추가 및 `_update_auto`에서 진행 정지 처리
  - 운영 로직 `apply_mode_action`에서 HOLD/RESUME/STOP에 따른 `paused/auto` 제어

변경 사항
- 수동조작 허용 조건: `sim.auto == NONE`일 때만 허용(기존 브리지 로직과 일치)
- HOLD 상태에서는 자동 진행만 멈추고 제어는 유지되므로 트렌드/상태는 계속 업데이트

수정파일
- sim/core/dcm_cryo_cooler_sim.py: `paused` 플래그 도입 및 `_update_auto` 가드 추가
- sim/logic/operating.py: HOLD/RESUME/STOP 처리 분기 업데이트

비고
- 기존 `_held` 플래그는 내부 상태 추적용으로 유지(동작에는 영향 없음)



2025-09-12 10:45:00 KST

작업 내역
- STOP(수동조작 모드)에서 V19 상태가 갱신되지 않는 문제 수정
  - 원인: `sim._update_levels()`에서 LT19 히스테리시스(30/40%)에 따라 V19를 자동 제어하여 수동 명령을 즉시 덮어씀
  - 조치: 자동 시퀀스 진행 중(`auto != NONE`이고 `paused=False`)에만 V19 자동 제어를 적용

변경 사항
- 수동 모드(STOP, 또는 AUTO=None)에서는 V19를 사용자가 직접 ON/OFF 가능하고, STATUS도 즉시 반영됨

수정파일
- sim/core/dcm_cryo_cooler_sim.py: `_update_levels()`에서 V19 자동 제어 조건부 처리로 변경

비고
- 다른 밸브들은 자동 히스테리시스가 없어서 정상 동작했던 것으로 판단



2025-09-12 10:58:00 KST

작업 내역
- `$(P)DCM:POWER`(= `BL:DCM:CRYO:DCM:POWER`) 값을 입력으로 받아 `q_dcm`에 적용
  - 브리지 루프에서 해당 PV를 읽어 `self.q_dcm`에 반영
  - 기존처럼 주기적으로 PV에 `q_dcm`을 써 덮어쓰는 동작 제거
  - 초기 기본값은 `config.q_dcm`로 설정 가능, 필요 시 `pv_init.yaml`의 `pvs:` 섹션에서 PV 값을 시드

변경 사항
- 운영자가 PV를 조정하면 즉시 열부하(`q_dcm`)에 반영되어 모델에 적용

수정파일
- tools/pv_bridge.py: DCM:POWER 주기적 put 제거, 매 루프 get하여 `q_dcm` 업데이트

비고
- DB에서는 `DCM:POWER`가 ai 타입이지만, 시뮬레이터에서는 입력으로 취급함(테스트 목적)



2025-09-12 11:08:00 KST

작업 내역
- GUI에서 `BL:DCM:CRYO:DCM:POWER` 값을 직접 입력할 수 있도록 입력 위젯 추가
  - `gui/bob/main.bob`: Power(W) 표시 옆에 `textentry` 추가(`$(P)DCM:POWER` 바인딩)

변경 사항
- 사용자는 GUI에서 열부하(W)를 입력하면 즉시 시뮬레이터에 반영됨

수정파일
- gui/bob/main.bob: `DCMPowerEntry` 위젯 추가

비고
- 기존 표시(`textupdate`)는 유지하여 현재값을 동시에 확인 가능



2025-09-12 11:16:00 KST

작업 내역
- `BL:DCM:CRYO:DCM:POWER`를 입력 가능하도록 DB 타입을 `ai`→`ao`로 변경
  - `db/dcm_cryo.db`, `DCM_CCV2App/Db/dcm_cryo.db` 모두 수정 (DRVL/DRVH 포함)

변경 사항
- GUI의 `textentry`가 정상 작동하여 사용자가 값을 쓸 수 있음

수정파일
- db/dcm_cryo.db
- DCM_CCV2App/Db/dcm_cryo.db

비고
- 브리지는 해당 PV를 입력으로 읽으므로 코드 변경 불필요



2025-09-12 11:28:00 KST

작업 내역
- 메인 화면에 유량/펌프 주파수 트렌드 그래프 추가
  - 히스토리 파형 PV 추가: `HIST:FLOW:FT18`, `HIST:FLOW:V17`, `HIST:FLOW:V10`, `HIST:PUMP:FREQ`
  - 브리지에 히스토리 버퍼 및 퍼블리시 로직 추가
  - GUI에 `FlowTrendChart`(xyplot) 추가하여 TIME vs 각 히스토리 파형 표시

변경 사항
- FT18/V10/V17 유량과 펌프 Hz의 시간 추세를 메인 화면에서 확인 가능

수정파일
- tools/pv_bridge.py: 히스토리 PV/버퍼 추가 및 퍼블리시
- db/dcm_cryo.db, DCM_CCV2App/Db/dcm_cryo.db: 신규 waveform 레코드 추가
- gui/bob/main.bob: `FlowTrendChart` 위젯 추가

비고
- 히스토리 길이는 기존과 동일(`NELM=2048`), 시간축은 `HIST:TIME` 사용



2025-09-12 16:01:23 KST

작업 내역
- `.codex/work-rules.md`의 한국어 응답/작업 규칙을 확인하고 전면 적용
  - 모든 응답은 한국어로 작성, 코드/식별자는 영어 유지
  - 작업 기록은 `docs/note_working.md`에 일관 포맷으로 누락 없이 축적

변경 사항
- 정책 적용(행동 원칙 변경)으로 기능/코드 변경 없음

수정파일
- (없음)

비고
- 이후 대화/설명은 한국어로 제공, 에러/로그는 원문 유지 + 한국어 설명 병행



작업내용: .codex/work-rules.md(작업 규칙) 확인 및 준수 선언. 한국어 응답 원칙, 코드/파일명/명령어 예외 규칙, 에러/로그 설명 방식, 작업 이력 기록 프로세스 적용.
변경사항: 리포지토리 기능 변경 없음. 작업 원칙 수립 및 기록만 수행.
수정파일: .codex/work-rules.md 열람, docs/note_working.md에 본 항목 추가.
추가 보완 및 비고: 이후 모든 응답은 한국어로 제공. pv_bridge.py=EPICS–시뮬레이터 중계, operating.py=시퀀스 관리, dcm_cryo_cooler_sim.py=물리 시뮬레이션 역할 구분 준수.



작업내용: 파라메타 튜닝/관리 개선. pv_bridge에 런타임 튜닝 PV 지원 추가, YAML 오버레이(tools/tuning.yaml) 병합 로직 및 설정값 검증/클램프 적용. 문서에 사용법 반영.
변경사항: 
- pv_bridge.py: TUNE PV 상수/초기화/루프 반영(_init_tuning_pvs, _apply_tuning_from_pvs) 추가, init-config 로딩 시 tools/tuning.yaml 오버레이 병합, _apply_config_with_validation로 파라메타 범위 검증 및 적용.
- docs/logic/DCM_CryoCooler_Simulator_README.md: 튜닝/설정 섹션(6.1/6.2) 추가.
- tools/tuning.yaml: 샘플 오버레이 파일 추가(주석 템플릿).
수정파일: tools/pv_bridge.py, docs/logic/DCM_CryoCooler_Simulator_README.md, tools/tuning.yaml
추가 보완 및 비고: IOC에 튜닝 PV가 없으면 자동으로 무시(선택적). 필요 시 DB에 해당 PV들을 정의하면 런타임 조정 가능. 기존 pv_init.yaml은 그대로 동작하며, tuning.yaml이 있을 경우에만 병합됨.



작업내용: DB에 튜닝 PV 추가, 초기 튜닝값을 tools/tuning.yaml로 이관.
변경사항:
- db/dcm_cryo.db: BL:DCM:CRYO:TUNE:* 계열(ao) 10종 추가(LT19 fill/cons/vent, LT23 refill/drain/cons/vent/heater 등). EGU/범위/표시 설정 포함.
- tools/pv_init.yaml: 세부 튜닝 키 제거(운영 기본만 유지), 주석으로 tuning.yaml로 이관 안내.
- tools/tuning.yaml: config 섹션에 기존 튜닝 초기값 반영(lt19_fill_lps, lt23_* 등).
수정파일: db/dcm_cryo.db, tools/pv_init.yaml, tools/tuning.yaml
추가 보완 및 비고: pv_bridge가 tuning PV를 자동 게시/반영하므로 IOC 기동 후 바로 UI에서 값 조정 가능. 중복 설정 충돌 방지를 위해 pv_init.yaml의 동일 키는 제거.
