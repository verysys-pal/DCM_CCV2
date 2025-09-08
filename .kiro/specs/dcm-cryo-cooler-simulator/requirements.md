# Requirements Document

## Introduction

DCM(Double Crystal Monochromator) Cryo Cooler 제어로직 시뮬레이터는 빔라인 DCM Cryo Cooler의 안전한 상태기계 기반 제어, 재현 가능한 실험, 자동화된 검증을 위한 통합 시스템입니다. 이 시스템은 EPICS IOC, CSS Phoebus GUI, 그리고 포괄적인 테스트 하네스를 포함하여 실제 운영 환경을 시뮬레이션하고 검증할 수 있는 완전한 플랫폼을 제공합니다.

## Requirements

### Requirement 1

**User Story:** 시스템 운영자로서, 나는 DCM Cryo Cooler의 상태를 안전하게 제어하고 모니터링할 수 있기를 원한다. 그래야 빔라인 운영 중 안전사고를 방지하고 최적의 성능을 유지할 수 있다.

#### Acceptance Criteria

1. WHEN 시스템이 시작되면 THEN 시스템은 OFF 상태에서 시작해야 한다
2. WHEN 운영자가 시작 명령을 내리면 THEN 시스템은 OFF → INIT → PRECOOL → RUN 순서로 상태 전이를 수행해야 한다
3. WHEN 비정상 상황이 감지되면 THEN 시스템은 즉시 SAFE_SHUTDOWN 상태로 전이해야 한다
4. WHEN ALARM 상태에서 운영자가 확인(ACK)하면 THEN 시스템은 안전 조건 만족 시 OFF 상태로 복귀해야 한다
5. WHEN RUN 상태에서 HOLD 요청이 있으면 THEN 시스템은 HOLD 상태로 전이하고 현재 온도를 유지해야 한다
6. WHEN WARMUP 요청이 있으면 THEN 시스템은 안전하게 상온까지 승온 후 OFF 상태로 전이해야 한다

### Requirement 2

**User Story:** 제어 엔지니어로서, 나는 EPICS 기반의 표준화된 인터페이스를 통해 시스템과 통신할 수 있기를 원한다. 그래야 기존 빔라인 제어 시스템과 통합할 수 있다.

#### Acceptance Criteria

1. WHEN EPICS IOC가 시작되면 THEN 모든 PV가 정의된 네이밍 규칙(BL:DCM:CRYO:{SIG}:{ATTR})에 따라 생성되어야 한다
2. WHEN 클라이언트가 PV에 접근하면 THEN Channel Access 또는 PV Access 프로토콜을 통해 통신이 가능해야 한다
3. WHEN 상태 PV가 업데이트되면 THEN 0=OFF, 1=INIT, 2=PRECOOL, 3=RUN, 4=HOLD, 5=WARMUP, 6=ALARM, 7=SAFE_SHUTDOWN 값으로 표현되어야 한다
4. WHEN 온도/압력/유량 PV가 업데이트되면 THEN 적절한 단위(K, bar, slpm)와 정밀도로 표시되어야 한다
5. WHEN 명령 PV에 값이 쓰여지면 THEN 해당 명령이 시뮬레이터에 즉시 반영되어야 한다

### Requirement 3

**User Story:** 운영자로서, 나는 직관적인 그래픽 인터페이스를 통해 시스템 상태를 모니터링하고 제어할 수 있기를 원한다. 그래야 효율적이고 안전한 운영이 가능하다.

#### Acceptance Criteria

1. WHEN CSS Phoebus GUI가 실행되면 THEN 메인 대시보드와 개략도 화면이 표시되어야 한다
2. WHEN 시스템 상태가 변경되면 THEN GUI의 상태 표시기가 실시간으로 업데이트되어야 한다
3. WHEN 알람이 발생하면 THEN GUI에서 시각적/청각적 경보가 표시되어야 한다
4. WHEN 운영자가 제어 버튼을 클릭하면 THEN 해당 명령이 EPICS PV를 통해 전송되어야 한다
5. WHEN 온도/압력 데이터가 업데이트되면 THEN 트렌드 차트가 실시간으로 갱신되어야 한다
6. WHEN 개략도 화면에서 THEN 배관, 밸브, 센서의 상태가 동적 색상과 애니메이션으로 표시되어야 한다

### Requirement 4

**User Story:** 시뮬레이션 엔지니어로서, 나는 실제 물리적 특성을 반영한 시뮬레이터를 통해 다양한 운영 시나리오를 테스트할 수 있기를 원한다. 그래야 실제 설비 운영 전에 충분한 검증을 수행할 수 있다.

#### Acceptance Criteria

1. WHEN 시뮬레이터가 실행되면 THEN 1차/2차 열용량 모델을 기반으로 온도 변화를 계산해야 한다
2. WHEN 냉각 부하가 변경되면 THEN 열역학적 모델에 따라 온도가 변화해야 한다
3. WHEN 환경 조건이 변경되면 THEN 시스템 응답이 실제 물리 법칙을 따라야 한다
4. WHEN 잡음이나 드리프트가 주입되면 THEN 센서 데이터에 현실적인 변동이 반영되어야 한다
5. WHEN 고장 상황이 주입되면 THEN 센서 NaN, 유량=0, 압력 이상 등의 상황이 시뮬레이션되어야 한다
6. WHEN 시간 스케일이 조정되면 THEN 실시간(1x) 또는 가속(10~100x) 모드로 실행되어야 한다

### Requirement 5

**User Story:** 테스트 엔지니어로서, 나는 자동화된 테스트 도구를 통해 시스템의 안전성과 신뢰성을 검증할 수 있기를 원한다. 그래야 모든 운영 시나리오에서 시스템이 안전하게 동작함을 보장할 수 있다.

#### Acceptance Criteria

1. WHEN 시나리오 테스트가 실행되면 THEN YAML 파일로 정의된 단계별 테스트가 자동으로 수행되어야 한다
2. WHEN 정상 시나리오가 실행되면 THEN 예상된 상태 전이와 성능 기준이 검증되어야 한다
3. WHEN 비정상 시나리오가 실행되면 THEN 인터락과 안전 기능이 올바르게 동작해야 한다
4. WHEN 프로퍼티 테스트가 실행되면 THEN 시스템 불변식이 모든 조건에서 유지되어야 한다
5. WHEN 퍼징 테스트가 실행되면 THEN 랜덤 입력에 대해 시스템이 안전하게 반응해야 한다
6. WHEN 테스트가 완료되면 THEN 상세한 리포트와 커버리지 정보가 생성되어야 한다

### Requirement 6

**User Story:** 시스템 관리자로서, 나는 인터락과 안전 기능이 모든 위험 상황에서 올바르게 동작하는지 확인할 수 있기를 원한다. 그래야 실제 운영 환경에서 안전사고를 예방할 수 있다.

#### Acceptance Criteria

1. WHEN 온도가 설정 한계를 초과하면 THEN 시스템은 즉시 안전 모드로 전환되어야 한다
2. WHEN 압력이 허용 범위를 벗어나면 THEN 압축기가 정지되고 퍼지 밸브가 개방되어야 한다
3. WHEN 유량이 최소값 이하로 떨어지면 THEN 일정 시간 내에 알람이 발생하고 SAFE_SHUTDOWN으로 전이되어야 한다
4. WHEN 센서에서 NaN 값이 감지되면 THEN 해당 채널이 무시되고 대체값이 사용되며 경보가 발생해야 한다
5. WHEN 다중 고장이 발생하면 THEN 가장 안전한 상태로 시스템이 전환되어야 한다
6. WHEN 안전 조건이 복구되면 THEN 운영자 확인 후에만 정상 운영이 재개되어야 한다

### Requirement 7

**User Story:** 개발자로서, 나는 모듈화된 아키텍처를 통해 시스템의 각 구성요소를 독립적으로 개발하고 테스트할 수 있기를 원한다. 그래야 유지보수성과 확장성을 확보할 수 있다.

#### Acceptance Criteria

1. WHEN 시스템이 구성되면 THEN 시뮬레이터 코어, EPICS IOC, GUI, 테스트 하네스가 독립적인 모듈로 분리되어야 한다
2. WHEN 모듈 간 통신이 필요하면 THEN 표준화된 인터페이스(PV, gRPC, CLI)를 통해 이루어져야 한다
3. WHEN 새로운 기능이 추가되면 THEN 기존 모듈에 영향을 주지 않고 확장 가능해야 한다
4. WHEN 단위 테스트가 실행되면 THEN 각 모듈이 독립적으로 테스트 가능해야 한다
5. WHEN 설정이 변경되면 THEN 런타임에 동적으로 적용 가능해야 한다
6. WHEN 로깅이 활성화되면 THEN 각 모듈의 상세한 디버그 정보가 기록되어야 한다