# 주요 장치별 목적과 사용 조건

본 문서는 Cryo 시스템의 주요 계측/구동 장치(PV 기준)를 목적과 사용(운전) 조건 관점에서 정리합니다. pv_bridge는 EPICS I/O 중계에 집중하고, 운전/조건 로직은 `sim/logic/operating.py`에서 관리합니다.

## 공통 원칙
- 명령(CMD)과 상태(STATUS)는 일대일로 미러링하며, 파생값(유량/개도/주파수/전력 등)은 운전 로직에서 계산합니다.
- 특정 밸브 조합에 따른 측정값 게이팅(예: 대기 개방 시 PT1=대기압, T5=주위온도)은 운전 로직에서 적용됩니다.
- 초기값은 `tools/pv_init.yaml`로 제공되며, 모델/운전 파라미터는 YAML 또는 코드 기본값으로 설정됩니다.

---

## 온도 (Temperature)
- 목적: 콜드헤드 및 DCM 주변의 열 상태 모니터링과 제어 목표(SETPOINT) 제공
- 관련 PV
  - `BL:DCM:CRYO:TEMP:SETPOINT` (ao): 운전 목표 온도
- `BL:DCM:CRYO:TEMP:T5` (ai): 콜드헤드/냉각부 대표 온도
  - `BL:DCM:CRYO:TEMP:T6` (ai): 다운스트림 온도 T6
  - `BL:DCM:CRYO:TEMP:SUBCOOLER` (ai): 서브쿨러 온도 Tsub
- 사용 조건/로직
  - 컨트롤러 유효 목표: `OFF/SAFE/WARMUP` 상태에서는 `SETPOINT` 대신 `Tamb(주위온도)`를 사용
  - T5 게이팅: `V9=0` AND `V21=1`(대기 개방)일 때 T5는 `Tamb`로 간주
  - 서브쿨러 Tsub는 모델과 표시 PV 모두에서 사용되며, 필요 시 YAML로 초기화

## 압력 (Pressure)
- 목적: 프로세스 라인의 압력 상태 모니터링 및 안전/운전 판단
- 관련 PV
  - `BL:DCM:CRYO:PRESS:PT1` (ai)
  - `BL:DCM:CRYO:PRESS:PT3` (ai)
- 사용 조건/로직
  - 기본 파생: `PT1/PT3`는 `tch`와 `tamb` 차이에 따른 단순 함수로 파생
  - 대기 개방 게이팅: `V9=0 & V21=1`일 때 `PT1=1.0`(대기압 근사)

## 유량 (Flow)
- 목적: 밸브/라인 유량 상태 파악 및 모델 영향
- 관련 PV
  - `BL:DCM:CRYO:FLOW:FT18` (ai): 외부 입력값(모델이 참조)
  - `BL:DCM:CRYO:FLOW:V17` (ai): V17 개도 기반 파생 유량
  - `BL:DCM:CRYO:FLOW:V10` (ai): V10 바이패스 유량(0/6 L/min)
- 사용 조건/로직
  - `FT18`은 외부에서 설정되며 모델이 읽어 T6 등에 영향
  - `V17:CMD`→ `V17(%)`→ `FLOW:V17` 순으로 파생(100%에서 약 8 L/min)
  - `V10:CMD`에 따라 0 또는 6 L/min로 단순 파생

## 밸브 (Valves)
- 목적: 라인 개폐 제어 및 운전 상태 전환
- 관련 PV
  - `BL:DCM:CRYO:VALVE:V9|V11|V15|V17|V19|V20|V21:CMD` (bo)
  - `BL:DCM:CRYO:VALVE:V9|V11|V15|V17|V19|V20|V21:STATUS` (bi)
  - `BL:DCM:CRYO:VALVE:V10:CMD/STATUS` (bo/bi)
  - `BL:DCM:CRYO:VALVE:V17` (ao, 0–100% 개도)
- 사용 조건/로직
  - STATUS는 CMD를 미러링(중계)
  - `V17`은 개도(%)와 유량이 파생
  - 게이팅 규칙: `V9=1`일 때 서브쿨러 LN2가 DCM 부하로 유입, `V9=0 & V21=1`일 때 라인 대기 개방

## 펌프 (Pump)
- 목적: 순환/공급 제어
- 관련 PV
  - `BL:DCM:CRYO:PUMP:CMD` (bo) → `RUNNING` (bi)
  - `BL:DCM:CRYO:PUMP:FREQ` (ao)
- 사용 조건/로직
  - `CMD=1`이면 `RUNNING=1`, `FREQ=pump_freq_on`(기본 60.0 Hz)
  - `CMD=0`이면 `RUNNING=0`, `FREQ=pump_freq_off`(기본 0.0 Hz)

## 레벨 (Level)
- 목적: 탱크/베셀 내 LN2 레벨 모니터링
- 관련 PV
  - `BL:DCM:CRYO:LEVEL:LT19`, `BL:DCM:CRYO:LEVEL:LT23` (ai)
- 사용 조건/로직
  - 기본값은 YAML로 초기화, 상세 동특성은 향후 모델 확장 시 반영 가능

## 히터 베셀 (Heater Vessel)
- 목적: 가열부 제어 및 보상
- 관련 PV
  - `BL:DCM:CRYO:HEATER:CMD` (bo) → `RUNNING` (bi)
  - `BL:DCM:CRYO:HEATER:POWER` (ao)
- 사용 조건/로직
  - `CMD=1`이면 `RUNNING=1`, `POWER=heater_power_on`(기본 30.0 W)
  - `CMD=0`이면 `RUNNING=0`, `POWER=heater_power_off`(기본 0.0 W)

## 서브쿨러 (Subcooler)
- 목적: 공급 LN2 서브쿨링 및 DCM 냉각 효율 확보
- 관련 PV
  - `BL:DCM:CRYO:TEMP:SUBCOOLER` (ai)
- 사용 조건/로직
  - 기본 운전에서 `V9=1`이면 서브쿨러에서 DCM 부하로 LN2가 흐름
  - 대기 개방(`V9=0 & V21=1`) 시 T5를 `Tamb`로 간주하여 실제 냉각 없음으로 취급

## 상태/알람 (State/Alarm)
- 목적: 전체 운전 상태 관리와 안전 판단
- 관련 PV
  - `BL:DCM:CRYO:STATE:MAIN` (mbbi), `STATE:TEXT` (stringin)
  - `BL:DCM:CRYO:CMD:MAIN` (mbbo)
  - `BL:DCM:CRYO:ALARM:MAX_SEVERITY` (mbbi)
  - `BL:DCM:CRYO:SAFETY:INTERLOCK` (bi)
- 사용 조건/로직
  - 상태 전이는 `OperatingLogic.next_state`가 결정(START/STOP/HOLD/RESUME/WARMUP/EMERGENCY/RESET)
  - 알람/인터록은 `sim/logic/interlock.py` 또는 간단 규칙(예: `tch > alarm_t_high`) 사용

## DCM 열부하 (DCM Power)
- 목적: 표시 및 모델 파라미터 동기화
- 관련 PV
  - `BL:DCM:CRYO:DCM:POWER` (ai)
- 사용 조건/로직
  - 모델의 `q_dcm`과 동기화하여 표시

---

## 설정/구성 파일
- `tools/pv_init.yaml`: 초기 PV/모델/운전 파라미터 설정
- `tools/operating.yaml`: 운전 로직 파라미터(선택)
- `tools/interlock.yaml`: 인터록/알람 파라미터(선택)

## 책임 분리 요약
- pv_bridge: EPICS I/O 중계, 모델 스텝, 히스토리 퍼블리시
- operating: 상태 전이, 컨트롤 목표, 측정/유량/출력 파생
- interlock: 안전 판단 및 최대 알람 등급 산출
