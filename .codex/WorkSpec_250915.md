# DCM Cryo Simulator — Control & Refill Work Spec (v1.0)
**Last Updated:** 2025-09-15 14:30 UTC+09:00

---

## 1. Purpose

1) **파일 책임 재정의**
- `operating.py` : 모드/명령 전이만 담당
- `Sequencer.py` : 모든 밸브 및 펌프 제어 + 표시값(FT18, T5, T6, LT19, LT23) 갱신의 단일 오너.
- `dcm_cryo_cooler_sim.py` : `Sequencer`가 요청할 때(`sim.step`)만 호출하여 물리(값 변경)를 적용.

2) **시퀀스 → 규칙(룰) 기반 전환**
- “단계 번호” 의존 제거. **밸브 1개 = 규칙 함수 1개**의 **독립 규칙(Independent Valve Rules)** 구조.
- 각 규칙은 **자신의 밸브만** 제어, 공통 조건은 헬퍼로 재사용.

3) **HV 리필 정책**
- **COOL_DOWN 진입 후**: 최초 1회 **V15 개방**으로 **LT23 = 90%** 까지 보충.
- 그 뒤에는 **LT23 < 40%**에서만 재보충(목표 **90%**), **COOL_DOWN 재보충 시**에는 **V9, V17, V20(펄스)** 가 **모두 활성**일 때만 V15 보충 허용(게이팅).
- **V20 펄스 주기 = 1.0 s** 유지.
- **REFILL_HV 모드**: **LT23 < 90%**이면 게이팅 없이 V15 보충 허용.
- **히스테리시스**: 트리거 **< 39%**, 해제 **≥ 41%**.

4) **SubCooler 리필 정책**
- **COOL_DOWN 진입 후**: 최초 1회 **V19 개방**으로 **LT19 = 90%** 까지 보충.
- 이후에는 **LT19 < 50%**에서만 재보충(목표 **90%**).
- **히스테리시스**: 트리거 **< 49%**, 해제 **≥ 51%**.

5) **DCM 냉각 목적 명시**
- 본 시뮬레이터의 1차 목적은 **DCM 부하 냉각**.
- **V9(LN2 SUPPLY) & V11(RETURN)** 이 **동시에 개방**되고 **V21(CLOSE)** 이어야 **DCM 루프(dcm_loop_on)** 가 성립하여 **FT18>0**, **T5/T6 변화**가 발생.
- **DCM:POWER[W]** 가 증가하면 **ΔT = T6−T5** 및 **LT19 소모율**이 증가.
- **V21=OPEN**이면 **대기 퍼지**되어 루프는 비활성(dcm_loop_on=False).

---

## 2. Signals & Roles

### 2.1 Controls (밸브/구동)
- **V9**: LN2 Supply (DCM로의 공급 경로 게이트)
- **V11**: Return (DCM에서의 귀환 경로 게이트)
- **V15**: HV 리필 밸브
- **V17**: 루프 벤트(감압, 개도율 0~1)
- **V19**: SubCooler 리필 밸브
- **V20**: HV 펄스 벤트(0/1 토글, 1.0s)
- **V21**: Purge/격리 밸브
- **pump_hz**: 펌프 주파수(최소 운전 확보)
- **V10**: 루프 유량 베이스라인 개도

### 2.2 States (표시/센서)
- **FT18**: 유량
- **T5**: DCM 전단(입구) 온도
- **T6**: DCM 후단(출구) 온도 (= T5 + POWER/(ṁ·cp))
- **LT19**: SubCooler 레벨
- **LT23**: HV 레벨
- (필요 시) 압력/히터/세트포인트: `press_ctrl_on`, `press_sp_bar`, `heater_u` 등

### 2.3 Inputs
- **auto(mode)**, **paused**, **dt**, **DCM:POWER[W]**

---

## 3. Independent Valve Rules (함수 단위 규칙)

> 모든 규칙은 **독립 함수**로 구현하며, **자신의 밸브만** 설정한다. 공통 조건은 헬퍼로 판정.

### 3.1 V9 — DCM Supply
- 냉각 필요 시 `V9 = OPEN`.
- PURGE/격리 또는 냉각 불필요 시 `V9 = CLOSE`.

### 3.2 V11 — DCM Return
- DCM 루프 성립을 위해 `V11 = OPEN` (V9와 동시 개방 보장).
- 유지보수/격리 시 `V11 = CLOSE`.

### 3.3 V21 — Purge
- 퍼지 조건에서만 `V21 = OPEN` → **dcm_loop_on=False**. 평시 `CLOSE`.

### 3.4 V15 — HV Refill (Open/Close 전용)
- **활성 조건**: `_hv_refill_active(state)`가 True **AND**
  - (**COOL_DOWN**) `_hv_refill_gating_ok(controls)` == True **OR**
  - (**REFILL_HV**) 모드(게이팅 불필요)
- 활성 시 `V15 = OPEN`, 비활성 또는 상한 도달 시 `V15 = CLOSE`.
- **초기 보충**: COOL_DOWN 진입 후 LT23<90% → 90% 도달 시 `_hv_initial_done=True`.
- **재보충**: COOL_DOWN 중 LT23<40% (히스테리시스 39↔41) → 90% 도달 시 종료.

### 3.5 V20 — HV Pulse Vent (토글 전용)
- `_hv_refill_active(state)`가 True일 때 **1.0 s** 주기로 `1 ↔ 0` 토글.
- 비활성 시 `0.0`으로 고정, 타이머/위상 리셋.

### 3.6 V17 — Loop Vent (감압/개도율)
- 냉각 진행도에 따라 개도율 조정(예: 100% → 35% → 0%).
- **COOL_DOWN 재보충 활성 시** 최소 개도(예: ≥ 0.1~0.35) 보장하여 게이팅 충족.

### 3.7 V19 — SubCooler Refill
- **초기 보충**: COOL_DOWN 진입 후 LT19<90% → 90% 도달 시 `_sc_initial_done=True`.
- **재보충**: LT19<50% (히스테리시스 49↔51) → 90% 도달 시 종료.
- 활성 시 `V19 = OPEN`, 비활성 시 `CLOSE`.

### 3.8 Pump/V10 — Baseline
- `pump_hz ≥ 30 Hz`, `V10 ≥ 0.6` 등 최소 운전 확보(튜닝 가능).

### 3.9 Press/Heater
- 일반 운전 시 `press_ctrl_on=True`로 목표압력 유지.
- **HV 보충 활성(COOL_DOWN/REFILL_HV)** 동안 충돌 시 일시 비활성화 가능.

---

## 4. DCM Loop & Physics

### 4.1 루프 성립(gating)
- `dcm_loop_on = (V9==OPEN) and (V11==OPEN) and (V21==CLOSE)`

### 4.2 물리 업데이트
- `Sequencer.update()` 말미에 `sim.step(dt, power_W=DCM:POWER)` 호출.
- `sim`은 밸브/펌프/압력 상태를 읽어 **FT18, T5, T6, LT19, LT23** 등을 갱신.
  - `dcm_loop_on=False` → FT18≈0, T5/T6 서서히 공급/주변으로 수렴, LT19 소모 ≈ 0
  - `dcm_loop_on=True` → FT18>0, `T6 = T5 + POWER/(ṁ·cp)`, LT19 감소(유량·잠열 기반)

### 4.3 표시 업데이트
- `sim.step` 직후의 상태를 UI/로그에 반영.

---

## 5. Update Order (권장 실행 순서)

1) `rule_pump_v10_baseline()`
2) `rule_v9_dcm_supply()` → `rule_v11_dcm_return()`
3) `rule_v17_loop_vent()`
4) `rule_v20_hv_pulse_vent(dt)`
5) `rule_v15_hv_refill()`
6) `rule_v19_subcool_fill()`
7) `rule_v21_purge()`
8) `rule_press_heater()`
9) `sim.step(dt, power_W)` → 표시 업데이트

---

## 6. Helpers & Internal States

- **모드 전환 감지**: `_last_auto`
- **HV**: `_hv_initial_done`, `_hv_recharge_active`, `_pulse_v20_timer`, `_pulse_v20_state`, `_hv_pulse_period=1.0s`
- **SC**: `_sc_initial_done`, `_sc_recharge_active`
- **헬퍼**
  - `_hv_refill_active(state)`
    - REFILL_HV: `LT23 < 90%` → True
    - COOL_DOWN: 초기 `LT23<90%`(90% 도달 시 완료), 재보충 `LT23<40%`(39↔41 히스테리시스)
  - `_hv_refill_gating_ok(controls)`
    - COOL_DOWN 재보충 시: `V9==OPEN and V17>0 and V20 토글중`
    - REFILL_HV: 항상 True
  - `_sc_refill_active(state)`
    - 초기 `LT19<90%`, 재보충 `LT19<50%`(49↔51 히스테리시스)

---

## 7. Acceptance Criteria

1) **초기 HV 보충**: COOL_DOWN 진입 후 LT23<90% → V9/V17 준비, V20 펄스, V15 OPEN → LT23≥90% ⇒ V15 CLOSE, V20=0.
2) **HV 재보충**: COOL_DOWN 중 LT23<40%(39↔41) → 게이팅 충족 시 V15 OPEN → LT23 90% 도달 시 종료.
3) **REFILL_HV 모드**: LT23<90%면 V15 OPEN(게이팅 불요).
4) **SubCooler**: LT19 초기 90% 1회, 이후 LT19<50%(49↔51)에서 재보충.
5) **DCM 루프**: V9/V11이 둘 다 열리고 V21이 닫힌 경우에만 FT18>0, T6>T5(ΔT>0).
6) **퍼지**: V21=OPEN 시 dcm_loop_on=False, 압력 대기압 수렴, FT18≈0, 냉각·소모 정지.
7) **표시 일관성**: 모든 표시값은 `sim.step` 직후 값과 일치.

---

## 8. Test Plan (요약)

- **시나리오 A — 초기 쿨다운**: LT23=30% → 초기 보충(90%) 완료 → 루프 활성 시 T5/T6 하강, FT18>0.
- **시나리오 B — HV 재보충**: 소비로 LT23=39% ↓ → 재보충 트리거 → 90% 도달 후 정지.
- **시나리오 C — SubCooler 재보충**: LT19=49% ↓ → 재보충 시작 → 90% 도달 후 정지.
- **시나리오 D — 퍼지**: V21=OPEN → FT18=0, ΔT→0, 압력 대기압 수렴.
- **경계/노이즈**: 39/41, 49/51 근처 히스테리시스 확인.
- **부하 스윕**: DCM:POWER 0→정격→상한에서 ΔT·소모율 증가 검증.

---

## 9. Non-goals & Constraints

- `operating.py` 변경 금지.
- 새로운 물리 모델 작성 금지(물리는 `dcm_cryo_cooler_sim.py`에 위임).
- 단계 카운터 기반 시퀀스 로직 확장 금지(규칙 기반으로 대체).

---

## 10. Suggested Signatures (예시)

```python
# Sequencer rules (each controls exactly one valve)
def rule_v9_dcm_supply(self) -> None: ...
def rule_v11_dcm_return(self) -> None: ...
def rule_v21_purge(self) -> None: ...
def rule_v15_hv_refill(self) -> None: ...
def rule_v20_hv_pulse_vent(self, dt: float) -> None: ...
def rule_v17_loop_vent(self) -> None: ...
def rule_v19_subcool_fill(self) -> None: ...
def rule_pump_v10_baseline(self) -> None: ...
def rule_press_heater(self) -> None: ...

# Helpers / states
def _hv_refill_active(self, s) -> bool: ...
def _hv_refill_gating_ok(self, u) -> bool: ...
def _sc_refill_active(self, s) -> bool: ...
```

---

*End of document.*
