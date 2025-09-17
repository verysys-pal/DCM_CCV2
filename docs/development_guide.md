# 개발 가이드

## 1. 프로젝트 개요
- **목표**: DCM(Double Crystal Monochromator) 크라이오 쿨러 제어 로직을 EPICS IOC와 시뮬레이터, GUI, 테스트 하네스로 통합하여 설계·검증·시연합니다.
- **구성 요소**
  - `DCM_CCV2App`: EPICS 데이터베이스와 지원 모듈을 포함한 IOC 애플리케이션.
  - `iocBoot/iocDCM_CCV2`: softIOC 기동 스크립트(`st.cmd`).
  - `sim/`: 제어 대상 물리 모델 및 운전 시퀀서를 제공하는 파이썬 시뮬레이터.
  - `gui/`: CSS Phoebus 화면 리소스.
  - `tests/`: `pytest` 기반 단위/시나리오 테스트와 `tests/tools/runner.py` 시나리오 실행기.
- **운영 방식**: 시뮬레이터 → EPICS IOC(PV) → GUI/테스트 툴 체인을 구성하여 제어 상태기계와 인터락을 반복 검증합니다.

## 2. 개발 환경 준비
### 2.1 필수 소프트웨어
| 구성 | 권장 버전 | 비고 |
|------|-----------|------|
| EPICS Base | R7.0.x | `configure/RELEASE`의 `EPICS_BASE` 기본 경로(`/usr/local/epics/EPICS_R7.0/base`)를 사용하거나 환경에 맞게 수정합니다. |
| synApps modules | R7 계열 | `SUPPORT` 경로를 `configure/RELEASE`에서 설정합니다. Sequencer(`SNCSEQ`) 모듈이 필요합니다. |
| Python | 3.10 이상 | `requirements.txt`에 정의된 패키지를 설치합니다. |
| CSS Phoebus | 0.5 이상 | GUI 검증 시 필요합니다. |
| Git | 최신 | 저장소 관리 및 코드 리뷰용. |

### 2.2 EPICS Base 및 지원 모듈 설정
1. EPICS Base R7.0.x와 필요한 synApps 모듈(Sequencer 포함)을 로컬 경로에 설치합니다.
2. `configure/RELEASE` 파일에서 `EPICS_BASE`, `SUPPORT`, `SNCSEQ` 경로가 실제 설치 위치와 일치하는지 확인합니다.
3. 경로 변경 후에는 최상위 디렉터리에서 `make rebuild`를 실행하여 의존성을 재생성하는 것이 안전합니다.

### 2.3 Python 가상환경 구성
1. 시스템에 Python 3.10 이상이 설치되어 있는지 확인합니다.
2. 프로젝트 루트에서 가상환경을 생성합니다.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. 의존성을 설치합니다.
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. IOC 또는 테스트 스크립트를 실행할 때는 가상환경을 활성화한 상태로 유지합니다.

### 2.4 선택 구성요소
- **EPICS CLI 도구**: `softIoc`, `caget`, `caput`, `pvget`, `pvput` 등을 PATH에 추가하면 디버깅에 도움이 됩니다.
- **Python 개발 도구**: `black`, `ruff`, `mypy` 등 추가 정적 분석기를 사용하면 코드 품질을 높일 수 있습니다.

## 3. 빌드 및 IOC 실행 절차
### 3.1 초기 설정 점검
1. `configure/RELEASE`가 앞 절차에서 설정한 경로를 가리키는지 확인합니다.
2. (선택) EPICS 환경 변수를 적용합니다.
   ```bash
   export EPICS_BASE=/usr/local/epics/EPICS_R7.0/base
   export PATH="${EPICS_BASE}/bin/${EPICS_HOST_ARCH}:$PATH"
   ```

### 3.2 EPICS 애플리케이션 빌드
1. 프로젝트 루트에서 다음 명령으로 전체 애플리케이션을 빌드합니다.
   ```bash
   make -sj
   ```
   - 첫 빌드 또는 의존성 경로 변경 시 `make rebuild`를 사용합니다.
2. 빌드가 성공하면 실행 파일은 `bin/<EPICS_HOST_ARCH>/DCM_CCV2`에 생성되고, 데이터베이스는 `db/` 하위에 배치됩니다.

### 3.3 IOC 실행
1. softIOC 실행 디렉터리로 이동합니다.
   ```bash
   cd iocBoot/iocDCM_CCV2
   ```
2. 필요 시 실행 권한을 확인합니다(`chmod +x st.cmd`).
3. IOC를 기동합니다.
   ```bash
   ./st.cmd
   ```
   - 스크립트는 `db/dcm_cryo.db`를 로드하고 `iocInit`을 호출하여 softIOC를 시작합니다.
4. 다른 터미널에서 `caget BL:DCM:CRYO:STATE:MAIN` 등의 명령으로 PV를 확인합니다.
5. IOC 종료 시에는 `Ctrl+C`로 softIOC 프로세스를 중단합니다.

### 3.4 개발 편의 팁
- `st.cmd` 상단의 shebang은 빌드 산출물(`bin/linux-x86_64/DCM_CCV2`)을 가리킵니다. 호스트 아키텍처가 다른 경우 실제 경로에 맞게 수정합니다.
- 추가 DB 또는 SNL을 로드하려면 `iocBoot/iocDCM_CCV2/st.cmd`에 `dbLoadRecords`/`seq` 문장을 추가하십시오.

## 4. 테스트 및 시뮬레이터 활용
### 4.1 자동화 테스트 실행
1. 가상환경을 활성화하고 프로젝트 루트에서 다음을 실행합니다.
   ```bash
   pytest
   ```
2. 테스트 작성 시 `tests/` 구조를 따라 시나리오 YAML(`tests/scenarios/*.yaml`) 또는 파이썬 테스트 파일을 추가합니다.
3. `pytest` 실행 전에는 IOC 또는 시뮬레이터가 테스트에서 요구하는 상태인지 확인합니다.

### 4.2 시나리오 실행기 사용
- EPICS IOC가 기동된 상태에서 사전 정의된 운전 시퀀스를 재현합니다.
    ```bash
    python -m tests.tools.runner --plan tests/scenarios/normal_start.yaml
    python -m tests.tools.runner --plan tests/scenarios/flow_loss.yaml
    ```
- YAML `steps`는 `set`, `wait`, `assert`, `sleep` 등을 지원하며, 필요한 PV와 조건을 자유롭게 작성할 수 있습니다.

### 4.3 파이썬 시뮬레이터 단독 실행
1. `sim/core/dcm_cryo_cooler_sim.py`는 제어 대상 물리 모델을 제공합니다. 연구 목적 또는 오프라인 튜닝 시 다음과 같이 사용할 수 있습니다.
    ```python
    from sim.core.dcm_cryo_cooler_sim import CryoCoolerSim, State, Controls

    state = State(T5=300.0, T6=300.0, PT1=1.0, PT3=1.0, LT19=80.0, LT23=60.0)
    controls = Controls(
        V9=True,
        V11=True,
        V19=True,
        V15=False,
        V21=False,
        V10=1.0,
        V17=0.0,
        V20=0.0,
        pump_hz=60.0,
        press_ctrl_on=True,
        press_sp_bar=3.0,
    )
    sim = CryoCoolerSim(state=state, controls=controls)
    sim.step(dt=1.0, power_W=150.0)
    ```
2. 시뮬레이터는 IOC와 분리되어 있으므로 실시간 제어와 병행할 때는 EPICS 브리지를 통해 상호작용합니다.

### 4.4 통합 검증 흐름
1. 시뮬레이터 또는 실제 장비를 구동합니다.
2. IOC를 실행하여 PV 인터페이스를 노출합니다.
3. CSS Phoebus에서 `gui/bob/main.bob`을 열어 상태를 시각화합니다.
4. 필요 시 `tests/tools/runner.py` 또는 `pytest`로 자동화 검증을 수행합니다.

## 5. 코드 기여 규칙
### 5.1 브랜치 전략
- `main` 브랜치는 항상 배포 가능한 상태로 유지합니다.
- 기능 개발은 `feature/<주제>` 브랜치, 버그 수정은 `fix/<이슈>` 브랜치 등 명확한 접두어를 사용하여 분기합니다.
- 장기 작업은 주기적으로 `main`을 리베이스하거나 병합하여 충돌을 최소화합니다.

### 5.2 커밋 및 코드 스타일
- 커밋 메시지는 명령형 현재형을 사용하고, 변경 이유와 범위를 간결하게 기술합니다.
- 파이썬 코드는 PEP 8을 따르며 타입 힌트를 권장합니다. 기존 모듈 구조와 공백/문자열 포맷을 유지합니다.
- EPICS DB/SNL 파일은 4칸 들여쓰기와 대문자 PV 네이밍(`BL:DCM:CRYO:*`) 규칙을 준수합니다.
- 문서 변경 시 Markdown 헤더 계층과 표/코드 블록 포맷을 점검합니다.

### 5.3 테스트와 문서화
- PR 생성 전에는 `pytest` 및 필요한 통합 테스트(시나리오 실행기 등)를 수행하고 결과를 공유합니다.
- 새로운 기능은 `docs/`에 개요, 운용 절차, 변경된 PV 목록 등을 업데이트합니다.

### 5.4 코드 리뷰 절차
1. 원격 저장소에 브랜치를 푸시하고 Pull Request를 생성합니다.
2. PR 설명에는 변경 요약, 테스트 결과, 관련 이슈/시나리오 링크를 포함합니다.
3. 최소 한 명 이상의 리뷰어 승인을 받은 후 `main`에 병합합니다.
4. 리뷰 중 제안된 수정 사항은 별도 커밋으로 반영하고, 필요 시 논의 내용을 문서에 기록합니다.

---

> 문의나 추가 개선 제안은 이슈 트래커에 등록하거나 슬랙/이메일 채널을 통해 공유해 주세요.
