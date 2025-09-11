# DCM Cryo‑Cooler Simulator (Python)

**Purpose**: This repository provides a **physics‑inspired discrete‑time simulator** of a Bruker‑type LN₂ **DCM Cryo‑Cooler** for operator/HMI logic prototyping, controls development, and interlock testing.

The model captures:
- Sub‑Cooler (LT19), Heater Vessel (LT23) with **HV heater‑based pressure control** (PT3 → PT1 coupling)  
- Pump frequency → **flow** (FT18) with **throttle V10** and **line valves V9/V11**  
- **Temperature dynamics** (T5 supply, T6 return) incl. boiling‑point vs pressure  
- **Automatic procedures**: **Cool‑down**, **Warm‑up**, **HV Auto‑Refill**  
- **Stop/Off** safety behavior and **READY** conditions

> GUI mapping aligns with *Figure 2 “GUI interface layout”*; operating steps & setpoints are taken from the manual’s expert/operator procedures, pressure/boiling‑point table, and readiness checklist. fileciteturn0file0

---
## Terminology — This System

### Auto Cool‑down (자동 냉각)
One‑button **automatic cool‑down** procedure that brings the loop and DCM to cryogenic operating state.  
It sequences valves/pump/pressure control to: pre‑purge and fill, initial open‑loop cool, closed‑loop cool,
enable **Pressure Control** (HV heater based) at the setpoint (≈2 bar recommended), adjust HV/Sub‑Cooler
levels (HV ≈25–30 %), and finally assert **System READY** once thresholds are met.

### Auto Warm‑up (자동 워밍업)
One‑button **automatic warm‑up** procedure that safely returns the loop to near‑ambient while preserving setup
for the next cool‑down. It isolates the consumer (V9/V11 CLOSE), partially vents the loop (V17), waits until
**PT1 < 1 bar**, then opens **V21 PURGE** with dry N₂ and continues until **T6 ≈ 280 K**, after which the purge
is stopped and vents are closed.

---
## 요약

### 1. 내용

- 신호/액츄에이터 맵핑:
    - `T5,T6,PT1,PT3,LT19,LT23,FT18` 
    ↔ `V9,V11,V10,V17,V19,V15,V20,V21,pump_hz,press_ctrl_on,press_sp_bar`
- 지배관계
    - 유량: `Q = 15*(Hz/80)*(0.4+0.6*V10)`
        - FT18는 `V11` 하류이므로 `V11=CLOSE`면 ≈0
    - 비등점:
        - `T_boil(PT1) ≈ 77 + 3.8·PT1` (0–5 bar 표 근사)
    - 온도:
        - `T_supply* = max(77, T_boil(PT1) − Δ_subcool·R_SC(LT19))`, `τ_cool ∝ 1/Q_eff`, `T6 = T5 + Power/(ṁ·c_p)`.
    - 레벨/소모:
        - 기본 3 L/h + 2.3 L/h/100W, 오픈루프(벤트) 시 추가 소모 패널티.
- 자동 시퀀스
    - Auto Cool‑down:
        - `V10=60%→Pump 30Hz→V19 purge→HV 90%→V9 OPEN,V17 100% (T6<200K)→V17 35% & V11 OPEN (T6<90K)→V17 CLOSE (T6<82K)→압력제어 ON(SP≈2bar)→HV 25–30% 맞춤→READY`
    - Auto Warm‑up:
        - `V9/V11 CLOSE → V17 일부 OPEN → PT1<1bar 시 V21 OPEN → T6=280K`
    - Auto Refill(HV):
        - `PressureCtrl OFF → V15 OPEN + V20 1s 펄스 → LT23≈25% → PressureCtrl ON`
- 상태기계:
    - `{IDLE, COOLING, READY, WARMUP, STOP, OFF}` 전이 로직과 STOP/Off 동작(Off는 V17/V20 개방 포함).
- READY 조건:
    - `V9&V11 OPEN ∧ Pump ON ∧ PressureCtrl ON ∧ |PT3−SP|,|PT1−SP|≈0 ∧ LT23>20% ∧ T5<80K`

---

### 2. 코드 구성

- 모듈: `dcm_cryo_cooler_sim.py`
    - `@dataclass Controls` / `State`
        - `PT3`는 히터 베셀 내부압력으로 정의, 히터 PI 제어기가 `press_sp_bar`로 맞춥니다.
        - 이 압력이 결합항 `Kc*(PT3−PT1)`로 루프압력(PT1)에 전달.
        - V20은 HV 벤트, V17/V21은 루프 벤트·퍼지에 의해 PT1↓. (압력–비등점/절차 근거)
    - 유량/온도/레벨 모델
        - `FT18 = Q_loop`(V9&V11 OPEN일 때만 유량 표시),
            - 초기 냉각은 `Q_eff`(V17를 통한 오픈루프)로 열수송만 반영.
            - HMI 위치상 `V11=CLOSE → FT18≈0`.
        - `T5`는 `T_supply*`로 1차 지연, `T6`는 열부하/질량유량으로 계산.
        - `LT19`/`LT23` 동역학과 오픈루프 패널티(벤트 유량 기여) 포함.
    - 자동 절차 내장
        
        `auto_cool_down()`, `auto_warm_up()`, `auto_refill_hv()`가 HMI 절차를 단계 상태(`stage`)로 실행.
        
    - 인터락/안전
        - HV 저레벨 `<5%` → 자동 Stop.
        - `PT1,PT3 ≤ PSV−0.5 bar`.
        - READY 판정은 매뉴얼의 체크리스트와 동등
---
### 3. 온도·유량 모델 (V11 영향 포함)

1. 유량(루프)
    
    $$
    Q\,[L/min]=\underbrace{15\cdot\frac{\mathrm{Hz}}{80}\cdot(0.4+0.6\,V10)}_{\text{펌프/스로틀}}\cdot \mathbf{1}_{(V9=OPEN)}\cdot \mathbf{1}_{(V11=OPEN)}
    $$
    
    - FT18=Q (측정 표시), V11=Close면 0.
2. 서브쿨러 냉원 여유와 T5
    
    $$
    T_{\text{supply}}=\max\big(77,\;T_{boil}(PT1)-\Delta_{\text{sub}}\cdot R_{SC}\big),\quad R_{SC}=f(LT19)
    $$
    
    - `R_SC∈[0,1]` (예: `R_SC=clip(LT19/40%,0,1)`), **LT19↓ → 냉각여유↓**.
3. T5 동역학
    - **루프 냉각(C2)**:
        
        $$
        \displaystyle \frac{dT5}{dt}=\frac{T_{\text{supply}}-T5}{\tau_c},\;\tau_c=\frac{k_\tau}{\max(Q,Q_{min})}
        $$
        
    - **오픈루프 냉각(C1)**: 위 식과 동일하되 
    **유효 유량** `Q_eff = 15*(Hz/80)*(0.4+0.6V10)*1_{V9}*1_{(V11\text{ or }V17)}` 사용
    (=V11이 닫혀도 V17이 열려있으면 유량 경로 존재).
    - **퍼지/가열(C4)**:
        
        $$
        \displaystyle \frac{dT5}{dt}=\frac{T_{amb}-T5}{\tau_{warm}}
        $$
        
        - τ는 V21, 냉원잔량 (LT19, Hz)에 따라 가변)
4. T6 계산
    
    $$
    T6=T5+\frac{P_{DCM}}{\dot m c_p}+ \Delta T_{\text{loss}},\quad \dot m\propto Q_{\text{eff}}
    $$
    
    - 전이점 **200K/90K/82K**에서 밸브·압력제어 단계 전환.
5. LT19(서브쿨러) 소모
    
    $$
    \frac{dLT19}{dt}=\frac{+Fill(V19)-\big(Base+0.023\,P_{DCM}+ \gamma\,Q_{\text{vent}}\big)}{V_{SC}}\cdot100
    $$
    
    - Open loop  (C1)에선 배기관 유량 $Q_{\text{vent}}$ 가 추가 소모를 만든다고 모델링(계수 `γ` 튜닝).
    - Base≈3 L/h, 0.023 L/h/100 W.





---

## 1) Signals & Actuators (HMI ↔ Simulator)

**Sensors**
- `T5 [K]` – supply temperature  
- `T6 [K]` – return temperature (phase‑in/version setpoints use 200K/90K/82K)  
- `PT1 [bar(g)]` – closed‑loop pressure  
- `PT3 [bar(g)]` – **Heater Vessel internal pressure** (controlled by HV heater)  
- `LT19 [%]` – Sub‑Cooler level (recommended 30–40, high alarm 94)  
- `LT23 [%]` – Heater Vessel level (nominal 25–30, `<5%` triggers Stop)  
- `FT18 [L/min]` – loop flow (downstream of **V11**)

**Valves / actuators**
`V9` (Forward), `V11` (Return), `V10` (Throttle 0–1), `V17` (Loop vent 0–1),  
`V19` (Sub‑Cooler fill), `V15` (HV fill), `V20` (HV vent 0–1), `V21` (Purge On/Off),  
`pump_hz` (0–80 Hz), `press_ctrl_on` & `press_sp_bar` (HV pressure setpoint).

**READY condition (summary)**  
`V9 & V11 OPEN ∧ Pump ON ∧ PressureCtrl ON ∧ |PT3−SP|<δ ∧ |PT1−SP|<δ ∧ LT23>20% ∧ T5<80K`.  
(“System ready” checklist.) fileciteturn0file0

---

## 2) Governing Relationships (discrete‑time)

### 2.1 Flow & Throttle
- `Q[L/min] = 15*(pump_hz/80)*(0.4 + 0.6*V10)` gated by `V9` and **`V11`** for **FT18**.  
- **Open‑loop** during initial cool‑down (`V11` closed, `V17` open): an **effective** flow `Q_eff` is used for thermal transport but **FT18≈0**. Max flow @ 80 Hz >15 L/min (device spec). fileciteturn0file0

### 2.2 Pressure & Boiling‑point
- LN₂ boiling point vs overpressure (0–5 bar) is taken from the table (77–96 K). We use a linear fit:  
  `T_boil(PT1) ≈ 77 + 3.8·PT1` for 0–5 bar.  
- **HV heater** raises **PT3**; loop pressure **PT1** follows via coupling (restricted by vents **V17/V21**). **HV vent V20** relieves PT3. Recommended loop SP ≈ **2 bar** (≥ needed +1 bar). fileciteturn0file0

### 2.3 Temperatures
- Target supply `T_supply* = max(77, T_boil(PT1) − Δ_subcool·R_SC)` where `R_SC∈[0,1]` scales with Sub‑Cooler level (LT19).  
- Dynamics (first‑order):  
  - Cooling: `dT5/dt = (T_supply* − T5)/τ_cool`, `τ_cool ∝ 1/Q_eff`  
  - Purge/warm: `dT5/dt = (T_amb − T5)/τ_warm` with `τ_warm` slowed by remaining cold reserve (LT19, pump).  
  - Return: `T6 = T5 + Power/(ṁ·c_p)` with `ṁ∝Q_eff`.

### 2.4 Levels
- Base consumption ~3 L/h + **~2.3 L/h per 100 W** heat‑load. Open‑loop (venting) adds a penalty term. fileciteturn0file0

---

## 3) Automatic Procedures

### 3.1 Auto Cool‑down (staged)
1. `V10=60%`, pump `30 Hz`; purge supply (`V19` short).  
2. Fill HV to ~90% (`V15` + `V20` pulse).  
3. `V9 OPEN`, `V17=100%` → wait for `T6<200K`.  
4. `V17→35%`, `V11 OPEN` → wait for `T6<90K`.  
5. `V17→0%` → wait for `T6<82K`.  
6. Pressure control **ON**, `SP≈2 bar`; adjust HV to 25–30% (by brief vent or refill).  
7. When READY conditions meet, signal **READY**. fileciteturn0file0

### 3.2 Auto Warm‑up
`V9/V11 CLOSE`, `V17` partly open; when `PT1<1 bar` → `V21 OPEN`; purge until `T6=280 K`. fileciteturn0file0

### 3.3 Auto Refill (HV)
`press_ctrl_off` → `V15 OPEN` + `V20` **1 s pulse** until `LT23≈25%` → `press_ctrl_on`. fileciteturn0file0

---

## 4) State Machine

`{IDLE, COOLING, READY, WARMUP, STOP, OFF}`  
Transitions follow the steps above; **Stop (<1 s)** closes V9/V11, sets V10=100%, Pump OFF, PressureCtrl OFF; **Off (≥2 s)** additionally opens V17/V20 for safe depressurization. fileciteturn0file0

---

## 5) Usage

```python
from dcm_cryo_cooler_sim import CryoCoolerSim, Controls, State

# Initial state & controls
s = State(T5=280, T6=280, PT1=1.0, PT3=1.0, LT19=40.0, LT23=30.0)
u = Controls(V9=False, V11=False, V10=0.6, V17=0.0, V19=False, V15=False,
             V20=0.0, V21=False, pump_hz=0.0, press_ctrl_on=False, press_sp_bar=2.0)

sim = CryoCoolerSim(s, u)

# Start automatic cool-down and run for, say, one simulated hour (3600 s)
sim.auto_cool_down()
for t in range(3600):
    sim.step(dt=1.0, power_W=300.0)   # 300 W consumer heat load
    if sim.state.ready:
        break

print(sim.state)
```

---

## 6) Assumptions & Tuning

- Linearized `T_boil(PT1)` in 0–5 bar range; volumes, heat capacities and coupling gains (`Kh, Kc, k_tau, Kp, Ki`) are **tunable**.  
- Flow vs frequency is scaled by a single anchor (`>15 L/min @ 80 Hz`).  
- Sub‑Cooler/HV volumes and V19/V15/V20 rates are configurable constants.

> All operating values, sequences and limits are based on the **Bruker Cryo‑Cooler Installation & Operation Manual** (cool‑down steps, warm‑up, auto‑refill, boiling‑point table, GUI & READY checklist). See pages around **p.14 (GUI), p.42–49 (procedures), p.43–44 (pressure/boiling), p.58 (READY)**. fileciteturn0file0

---

## 7) Disclaimer

This simulator is **for engineering prototyping**. It is not a substitute for safety interlocks. Verify every interlock and threshold on the real system before operation.
