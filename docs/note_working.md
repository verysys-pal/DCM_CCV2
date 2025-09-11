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
