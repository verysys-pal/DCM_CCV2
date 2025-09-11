# DCM Cryo Cooler 제어로직 시뮬레이터 (EPICS IOC + CSS Phoebus + Test Harness)

> 본 저장소는 **DCM(Double Crystal Monochromator) Cryo Cooler** 제어로직의 설계·검증·시연을 위한 **시뮬레이터**와 **EPICS IOC**, **CSS Phoebus GUI**, **제어로직 시험용 프로그램**(테스트 하네스)을 제공합니다.
> 목표는 **안전한 상태기계 기반 제어**, **재현 가능한 실험**, **자동화된 검증(유닛/프로퍼티/퍼징)**, **운영 절차 검증**입니다.
> 제작 및 검증 과정에는 현재 Reference 폴더의 7개의 파일들을 필히 적용한다.


---

## 1) 개요

- **대상**: 빔라인 DCM Cryo Cooler (압축기, 콜드헤드, 퍼지/가스 라인, 온도/압력/유량 센서 포함)
- **범위**
  - 제어로직(State Machine) 설계 및 시뮬레이션
  - EPICS IOC(softIOC)로 PV 인터페이스 제공
  - CSS Phoebus GUI(.bob)로 HMI 제공
  - 시험용 프로그램(시나리오 드라이버, 퍼징, 프로퍼티 테스트)
  - 각 파트별/통합 검증, 퍼징 방법 검증, 운전 절차 검증

### 아키텍처 (개략)
```
+------------------+      PV (CA/PVA)      +---------------------+      PV       +---------------------+
|  Simulator Core  | <-------------------> |      EPICS IOC      | <-----------> |  CSS Phoebus (GUI)  |
|  (C/Python)      |                       |  (softIoc + DB/SNL) |               |  + Test Dashboards  |
+------------------+                       +---------------------+               +---------------------+
        ^                                                                                   ^
        | gRPC/CLI/Test API                                                                 |
        |                                                                                    |
        +--------------------+  퍼징/시나리오/프로퍼티  +------------------------------------+
                             |  Test Harness (Python, pyepics/p4p)
                             +------------------------------------+
```

---

## 2) 기능 목록

- **상태기계 기반 제어로직**
  - `OFF → INIT → PRECOOL → RUN → HOLD → WARMUP → OFF` (ALARM/FAULT 시 `SAFE_SHUTDOWN`)
  - 인터락(Interlock) 및 이상 상황 처리(온도/압력 한계, 유량 저하 등)
- **EPICS IOC**
  - SoftIOC + DB + (선택) SNL(Sequencer) 또는 State Notation (snc)
  - 표준 Record(ai/ao/bi/bo/calc/mbbi/mbbo/alarm)
- **CSS Phoebus GUI**
  - GUI 폴더의 파일 참고로 화면 업데이트
  - 상태/경보/트렌드/버튼/운전 절차 가이드 화면
- **시험용 프로그램**
  - 시나리오 실행기(정상/비정상)



---

## 4) 요구사항

- **EPICS Base 7.x** (softIoc, sequencer 사용 `SNCSEQ`)
- **Python 3.10+**, `pyepics` 또는 `p4p`, `pytest`, `hypothesis`
- CSS **Phoebus** (0.5+ 권장)

---

## 6) EPICS IOC

### 6.1 PV 네이밍 규칙
`BL:DCM:CRYO:{SIG}:{ATTR}` (예시)
- 예: `BL:DCM:CRYO:TEMP:T5`, `BL:DCM:CRYO:PRESS:PT1`, `BL:DCM:CRYO:EQUIP:COMPRESSOR`, `BL:DCM:CRYO:STATE:MAIN`, `BL:DCM:CRYO:ALARM:ACTIVE`

### 6.2 주요 PV 목록(발췌)

| PV | 타입 | 단위 | 설명 |
|---|---|---|---|
| `BL:DCM:CRYO:STATE:MAIN` | `mbbi` | - | 0=OFF,1=INIT,2=PRECOOL,3=RUN,4=HOLD,5=WARMUP,6=SAFE_SHUTDOWN,7=ALARM |
| `BL:DCM:CRYO:CMD:MAIN` | `mbbo` | - | 0=NONE,1=START,2=STOP,3=HOLD,4=RESUME,5=EMERGENCY_STOP,6=RESET |
| `BL:DCM:CRYO:EQUIP:COMPRESSOR` | `bo` | - | 압축기 On/Off 명령 |
| `BL:DCM:CRYO:VALVE:V9:CMD` | `bo` | - | 퍼지 밸브 (alias: `...:PURGE:CMD`) |
| `BL:DCM:CRYO:TEMP:SETPOINT` | `ao` | K | 목표 온도(Setpoint) |
| `BL:DCM:CRYO:PRESS:PT1` | `ai` | bar | 고압 측 압력 |
| `BL:DCM:CRYO:PRESS:PT3` | `ai` | bar | 저압 측 압력 |
| `BL:DCM:CRYO:PRESS:PT3:SP` | `ao` | bar | PT3 압력 설정값 (제어 목표) |
| `BL:DCM:CRYO:FLOW:FT18` | `ai` | L/min | 유량 |
| `BL:DCM:CRYO:ALARM:ACTIVE` | `calcout` | - | 활성 알람 여부 |
| `BL:DCM:CRYO:ALARM:ACK_ALL` | `bo` | - | 모든 알람 확인 |

### 6.3 DB 예시 (`DCM_CCV1App/Db/dcm_cryo.db` 발췌)
```db
record(mbbi, "BL:DCM:CRYO:STATE:MAIN") {
    field(ZRST, "OFF")
    field(ONST, "INIT")
    field(TWST, "PRECOOL")
    field(THST, "RUN")
    field(FRST, "HOLD")
    field(FVST, "WARMUP")
    field(SXST, "SAFE_SHUTDOWN")
    field(SVST, "ALARM")
}

record(mbbo, "BL:DCM:CRYO:CMD:MAIN") {
    field(ZRST, "NONE")
    field(ONST, "START")
    field(TWST, "STOP")
    field(THST, "HOLD")
    field(FRST, "RESUME")
    field(FVST, "EMERGENCY_STOP")
    field(SXST, "RESET")
    # WARMUP 명령은 CMD:MODE=Warm-up과 결합하여 사용 (CMD:MAIN에는 없음)
}

record(ai,  "BL:DCM:CRYO:TEMP:T5")       { field(EGU,"K") field(PREC,"2") }
record(ao,  "BL:DCM:CRYO:TEMP:SETPOINT") { field(EGU,"K") field(PREC,"2") field(DRVH,"300") field(DRVL,"4") }
record(calcout, "BL:DCM:CRYO:ALARM:ACTIVE") { field(CALC,"A>0") }
record(bo,  "BL:DCM:CRYO:ALARM:ACK_ALL")  { field(ZNAM,"Idle") field(ONAM,"AckAll") }
```

### 6.4 SNL 상태기계 초안 (`ioc/snl/dcm_cryo.stt`)
```c
program dcm_cryo
option +r; /* reentrant */
ss main {
  state OFF {
    when (cmd_start)    { /* 초기화 준비 */ } state INIT
  }
  state INIT {
    when (init_done)    { } state PRECOOL
    when (fault)        { } state SAFE_SHUTDOWN
  }
  state PRECOOL {
    when (t_coldhead < T_SP - 5) { } state RUN
    when (fault)              { } state SAFE_SHUTDOWN
  }
  state RUN {
    when (hold_req)    { } state HOLD
    when (warmup_req)  { } state WARMUP
    when (fault)       { } state SAFE_SHUTDOWN
  }
  state HOLD {
    when (resume_req)  { } state RUN
    when (fault)       { } state SAFE_SHUTDOWN
  }
  state WARMUP {
    when (t_chead > ambient - 5) { } state OFF
    when (fault)                 { } state SAFE_SHUTDOWN
  }
  state SAFE_SHUTDOWN {
    when (ack_clear && safe) { } state OFF
  }
}
```

---

## 7) 시뮬레이터 코어

- **동특성**: 1차 지연 + 열용량 모델 (예: `dT/dt = (T_env - T)/τ_env + Q_cool/Cap - Q_load/Cap`)

예시(Python, 발췌 `sim/core/model.py`)
```python
class CryoPlant:
    def __init__(self, cap=800.0, tau_env=120.0):
        self.T = 300.0
        self.cap = cap
        self.tau_env = tau_env
    def step(self, Tsp, Qload, dt):
        Qcool = self._controller(Tsp)
        dT = (300.0 - self.T)/self.tau_env + (Qload - Qcool)/self.cap
        self.T += dT * dt
        return self.T
```

---

## 8) CSS Phoebus GUI

- `gui/bob/main.bob`: 요약 대시보드(상태, 알람, 주요 온도/압력, 운전 버튼)
- `gui/bob/synoptic.bob`: 배관/밸브/센서 개략도, 동적 색상/애니메이션
- **실행**: `phoebus -resource gui/bob/main.bob`

---

## 9) 제어로직 시험용 프로그램 (Test Harness)

### 9.1 의존성
`pyepics`(CA) 또는 `p4p`(PVA), `pytest`, `hypothesis`

`requirements.txt` 예시:
```
pyepics>=3.5
p4p>=4.2
pytest>=8.0
hypothesis>=6.100
rich
```

### 9.2 시나리오 실행기
```bash
# 정상 시나리오
python -m tests.tools.runner --plan tests/scenarios/normal_start.yaml
# 비정상(인터락) 시나리오
python -m tests.tools.runner --plan tests/scenarios/flow_loss.yaml
```

`normal_start.yaml` 예시
```yaml
steps:
  - set: { pv: BL:DCM:CRYO:TEMP:SETPOINT, value: 80 }
  - set: { pv: BL:DCM:CRYO:CMD:MAIN, value: 1 }   # START
  - wait: { pv: BL:DCM:CRYO:STATE:MAIN, equals: 2, timeout: 60 }   # PRECOOL
  - wait: { pv: BL:DCM:CRYO:STATE:MAIN, equals: 3, timeout: 600 }  # RUN
  - assert: { pv: BL:DCM:CRYO:TEMP:T5, max: 85 }
```

### 9.3 프로퍼티 테스트(불변식)
- `ALARM:ACTIVE==0` 이면 `SAFE_SHUTDOWN` 상태가 아님
- `RUN` 상태에서 `TEMP:T5` 오차가 허용 범위(±Δ)
- 압력 한계 초과 시 일정 시간 내 `ALARM=1` 및 상태 전이

`pytest` + `hypothesis` 샘플
```python
from hypothesis import given, strategies as st

@given(st.floats(min_value=20, max_value=250))
def test_sp_tracks_setpoint(sp):
    set_pv("BL:DCM:CRYO:TEMP:SETPOINT", sp)
    # ... run for N seconds ...
    assert abs(get_pv("BL:DCM:CRYO:TEMP:T5") - sp) < 10
```


## 10) 운전 절차(동작 방법) 검증

### 10.1 정상 시나리오(예)
1. `TEMP:SETPOINT=80K` 설정 → `CMD:MAIN=1`
2. `INIT→PRECOOL→RUN` 자동 전이 확인
3. 안정화 후 편차 ±5K 이내 유지

### 10.2 비정상/인터락 시나리오
- **유량=0**: 일정 시간 내 `ALARM:ACTIVE=1`, `SAFE_SHUTDOWN` 진입
- **고압 과상승**: 압축기 정지, 퍼지 밸브 개방, 오퍼레이터 확인 요구
- **센서 NaN**: 해당 채널 무시/대체 값, 경보 발생

### 10.3 회복 절차
- 원인 제거 → `ALARM:ACK_ALL=1` → 상태 `OFF` 복귀 → 재시동



---

## 13) 트러블슈팅

- **IOC가 뜨지 않음**: `EPICS_BASE` 경로/권한 확인, `st.cmd` 로그 확인
- **PV 미갱신**: 네트워크 브로드캐스트/CA 검색, PVA 사용시 `p4p` 설정 확인
- **GUI 경보 미표시**: Phoebus Alarm Server 설정, PV 이름 불일치 확인

---
