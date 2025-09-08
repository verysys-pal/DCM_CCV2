# Implementation Plan

## 1. 프로젝트 구조 및 기본 인터페이스 설정

- [x] 1.1 프로젝트 디렉터리 구조 생성
  - Reference Guide에 따른 디렉터리 구조 생성 (sim/, gui/, tests/, tools/)
  - 기본 requirements.txt 및 Python 환경 설정
  - _Requirements: 7.1, 7.2_

- [x] 1.2 기본 데이터 모델 및 인터페이스 정의
  - SimulatorState, ControlCommands, SensorReadings 데이터 클래스 구현 (Python)
  - CryoConfig, ThermalConfig, SensorConfig, SafetyLimits 설정 모델 구현
  - _Requirements: 7.1, 7.2_

## 2. 시뮬레이터 코어 구현 ✅

- [x] 2.1 Bruker 기반 물리 모델 구현
  - BrukerCryoModel 클래스 구현 (다중 온도 존, LN2 시스템, 밸브 제어)
  - 열역학 계산 엔진 구현 (냉각, 가열, 환경 열부하)
  - LN2 시스템 모델링 (레벨, 유량, 냉각 파워 계산)
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 2.2 센서 시뮬레이션 구현
  - 온도 센서 (T5, T6, Cold Head) 시뮬레이션
  - 압력 센서 (PT1, PT3) 시뮬레이션
  - 레벨 센서 (LT19, LT23) 시뮬레이션
  - 유량 센서 (FT18) 시뮬레이션
  - 센서 노이즈, 드리프트, 지연 모델링
  - _Requirements: 4.4, 4.5_

- [x] 2.3 밸브 및 액추에이터 시뮬레이션
  - 시스템 다이어그램 기반 밸브 모델 (V9, V15, V19, V20, V21, V24)
  - 체크 밸브 (CV10, CV11, CV17) 동작 모델링
  - 압축기 모터 및 순환 펌프 시뮬레이션
  - 히터 제어 시스템 모델링
  - 밸브 스틱션 및 응답 지연 구현
  - _Requirements: 4.1, 4.6_

- [x] 2.4 고장 주입 시스템 구현
  - 센서 고장 주입 (NaN, 고정값, 드리프트, 스파이크)
  - 밸브 고장 주입 (스틱, 위치 오류, 응답 없음)
  - 장비 고장 주입 (압축기, 펌프, 히터 고장)
  - LN2 공급 중단 시나리오
  - 진단 세미나 기반 실제 고장 사례 구현
  - _Requirements: 4.5, 6.5_

- [x] 2.5 시뮬레이터 코어 통합
  - CryoSimulatorCore 메인 클래스 구현
  - 상태 기계 및 제어 로직 구현
  - 스레드 기반 실시간 시뮬레이션
  - 안전 시스템 및 알람 처리
  - 통계 및 히스토리 관리
  - _Requirements: 7.1, 7.2_

## 3. EPICS IOC 구현

- [x] 3.1 EPICS 데이터베이스 생성
  - DCM_CCV1App/Db/dcm_cryo.db 파일 생성
  - 시스템 다이어그램 기반 PV 구조 구현 (BL:DCM:CRYO:{SIG}:{ATTR} 네이밍)
  - 상태 제어 레코드 (STATE, CMD 시리즈) - mbbi/mbbo 타입
  - 온도/압력/레벨/유량 모니터링 레코드 - ai 타입
  - 밸브 제어 레코드 (V9~V24) - bo 타입
  - 장비 제어 레코드 (압축기, 펌프, 히터) - bo/ao 타입
  - 안전 및 알람 시스템 레코드 - bi/bo 타입
  - 한국어 알람 메시지 지원 레코드 추가
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3.2 EPICS 데이터베이스 Makefile 업데이트
  - DCM_CCV1App/Db/Makefile에 dcm_cryo.db 추가
  - st.cmd 파일에서 dbLoadRecords 라인 활성화
  - _Requirements: 2.1, 2.2_

- [x] 3.3 SNL 상태기계 구현
  - DCM_CCV1App/src/dcm_cryo.stt 파일 생성
  - OFF → INIT → PRECOOL → RUN → HOLD → WARMUP → OFF 상태 전이
  - SAFE_SHUTDOWN 및 ALARM 상태 처리
  - 안전 인터락 로직 구현
  - 상태별 밸브 및 장비 제어 로직
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 3.4 SNL 빌드 설정
  - DCM_CCV1App/src/Makefile에 SNL 지원 추가 (SNCSEQ 모듈 의존성)
  - configure/RELEASE에 SNCSEQ 경로 설정
  - st.cmd에서 seq 프로그램 시작 설정
  - _Requirements: 2.4, 2.5_

- [x] 3.5 Device Support 구현
  - 시뮬레이터와 EPICS IOC 간 통신 인터페이스 (asyn 기반)
  - PV 값 업데이트 및 명령 전달 메커니즘
  - 실시간 데이터 동기화
  - _Requirements: 2.4, 2.5, 7.2_

- [x] 3.6 비례제어밸브(PCV) 구현
  - Reference 문서 기반 PCV 제어 로직
  - 위치 피드백 및 제어 모드 구현
  - PCV 관련 PV 및 제어 알고리즘
  - _Requirements: 2.1, 2.5_

## 4. CSS Phoebus GUI 구현 ✅

- [x] 4.1 GUI 디렉터리 구조 생성
  - gui/bob/ 디렉터리 생성
  - gui/assets/ 디렉터리 생성 (이미지 및 리소스용)
  - Reference 이미지 파일들을 assets로 복사
  - _Requirements: 3.1, 7.1_

- [x] 4.2 메인 대시보드 화면 구현 (한국어 인터페이스)
  - gui/bob/main.bob 파일 생성
  - 시스템 상태 표시기 (색상 코딩, 한국어 라벨) - Text Update, LED 위젯
  - 온도/압력/레벨/유량 트렌드 차트 - XYPlot 위젯
  - 제어 버튼 (시작/정지/홀드/재개, 한국어 라벨) - Action Button 위젯
  - 알람 패널 및 확인 기능 (한국어 메시지) - Alarm Table 위젯
  - KPI 표시 및 LN2 공급 상태
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4.3 시놉틱 뷰 화면 구현
  - gui/bob/synoptic.bob 파일 생성
  - Cryocooler_image1.png 기반 시스템 레이아웃 - Symbol Builder 위젯
  - 실시간 밸브 위치 표시 (V9~V24, CV10~CV17)
  - 센서 데이터 실시간 표시 (T5, T6, PT1, PT3, LT19, LT23, FT18)
  - 장비 상태 표시 (압축기, 펌프, 히터)
  - 유동 방향 애니메이션 및 색상 코딩
  - 안전 시스템 상태 표시
  - 한국어 라벨 및 단위 표시
  - _Requirements: 3.5, 3.6_

- [x] 4.4 알람 및 진단 화면 구현
  - gui/bob/alarm.bob 파일 생성
  - 알람 테이블 및 이력 관리 (한국어 메시지)
  - 진단 정보 표시 (센서 상태, 밸브 위치, 장비 상태)
  - 시스템 성능 모니터링 차트
  - _Requirements: 3.3, 6.1, 6.2, 6.3_

## 5. 안전 시스템 및 인터락 구현 ✅

- [x] 5.1 온도 안전 인터락 구현
  - 최대/최소 온도 한계 모니터링 (경고/알람/치명적 3단계)
  - 온도 변화율 감시 (50K/min 임계값)
  - 과열 방지 로직 (히터 베셀)
  - 온도 한계 초과 시 자동 SAFE_SHUTDOWN
  - _Requirements: 6.1, 6.6_

- [x] 5.2 압력 안전 시스템 구현
  - 고압/저압 한계 모니터링 (다단계 임계값)
  - 압력 스파이크 감지 (5bar/s 임계값)
  - 압력 이상 시 퍼지 밸브(V9) 자동 개방
  - 압축기 자동 정지 로직
  - _Requirements: 6.2, 6.6_

- [x] 5.3 LN2 및 유량 안전 시스템 구현
  - LN2 레벨 모니터링 및 저레벨 경고 (다단계)
  - 최소 유량 감시 (FT18, 상태별 임계값)
  - 유량 저하 시 알람 및 SAFE_SHUTDOWN
  - LN2 공급 중단 감지 및 대응 (10초 지연)
  - _Requirements: 6.3, 6.6_

- [x] 5.4 센서 고장 감지 및 처리
  - 센서 NaN 값 감지 (3회 연속)
  - 센서 고정값 감지 (10회 연속)
  - 센서 드리프트 감지 (온도 50K/min)
  - 센서 스파이크 감지 (5σ 임계값)
  - 다중 센서 고장 인터락
  - _Requirements: 6.4, 6.6_

## 6. 테스트 하네스 구현 ✅

- [x] 6.1 테스트 환경 설정
  - tests/ 디렉터리 구조 생성 (scenarios/, fuzz/, properties/, tools/)
  - requirements.txt에 테스트 의존성 추가 (pyepics, p4p, pytest, hypothesis)
  - 기본 테스트 설정 및 유틸리티 모듈 구현 (conftest.py, utils.py)
  - 한국어 테스트 로그 및 리포트 지원
  - _Requirements: 5.1, 7.1_

- [x] 6.2 시나리오 실행기 구현
  - tests/tools/runner.py 구현
  - YAML 기반 테스트 시나리오 파서 (한국어 설명 지원)
  - pyepics/p4p 기반 PV 제어 인터페이스 (시뮬레이터 직접 모드 포함)
  - 단계별 테스트 실행 및 검증
  - 테스트 결과 리포팅 (한국어)
  - _Requirements: 5.1, 5.2_

- [x] 6.3 정상 운영 시나리오 구현
  - tests/scenarios/normal_start.yaml 생성 (정상 시작 시퀀스)
  - tests/scenarios/temperature_tracking.yaml 생성 (온도 설정점 추적)
  - tests/scenarios/state_transitions.yaml 생성 (상태 전이 검증)
  - 성능 기준 검증 테스트 포함
  - _Requirements: 5.2, 5.6_

- [x] 6.4 비정상 및 인터락 시나리오 구현
  - tests/scenarios/fault_scenarios/ 디렉터리 생성
  - 온도/압력 한계 초과 시나리오 (temp_limit.yaml, pressure_limit.yaml)
  - 유량 손실 시나리오 (flow_loss.yaml)
  - 센서 고장 시나리오 (sensor_fault.yaml)
  - LN2 공급 중단 시나리오 (ln2_loss.yaml)
  - 진단 세미나 기반 실제 고장 사례 포함
  - _Requirements: 5.2, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6.5 프로퍼티 기반 테스트 구현
  - tests/properties/test_invariants.py 구현
  - hypothesis 기반 랜덤 입력 생성 및 전략 정의
  - 시스템 불변식 검증 (안전 조건, 상태 일관성, 센서 관계)
  - 경계값 테스트 및 상태 기반 테스트 머신
  - 장시간 안정성 테스트
  - _Requirements: 5.4, 5.6_

- [x] 6.6 퍼징 테스트 구현
  - tests/fuzz/fuzzer.py 구현 (다중 전략 지원)
  - 랜덤 제어 입력 생성 (경계값, 변형, 가이드 전략)
  - 안전 불변식 모니터링 및 위반 감지
  - 실패 케이스 최소화 및 재현 기능
  - 커버리지 측정 및 리포팅 (상태, 센서 범위)
  - tests/fuzz/artifacts/ 디렉터리 생성 (결과 저장용)
  - _Requirements: 5.5, 5.6_

## 7. 통합 및 검증

- [x] 7.1 시스템 통합 테스트
  - 시뮬레이터-IOC-GUI 전체 연동 테스트
  - 실시간 성능 검증
  - 메모리 사용량 및 안정성 테스트
  - _Requirements: 7.3, 7.4_

- [x] 7.2 사용자 시나리오 검증
  - 운영자 워크플로우 테스트 (정상 시작 시퀀스 검증)
  - GUI 사용성 검증 (접근성, 한국어 지원, 직관성)
  - 알람 및 대응 절차 검증 (알람 시스템 및 운영자 대응)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 7.3 성능 및 확장성 테스트
  - 다중 클라이언트 연결 테스트 (10개 동시 클라이언트)
  - 고빈도 PV 업데이트 테스트 (10Hz 업데이트)
  - 장시간 운영 안정성 테스트 (메모리 누수 감지)
  - 리소스 사용량 모니터링 (CPU, 메모리, 디스크)
  - _Requirements: 7.5, 7.6_

- [x] 7.4 문서화 및 배포 준비
  - 사용자 매뉴얼 작성 (한국어) - 완료
  - 설치 및 설정 가이드 작성 (한국어) - 완료
  - API 문서 생성 - 완료
  - README 업데이트 - 완료
  - _Requirements: 7.6_

## 8. 고급 기능 구현 ✅

- [x] 8.1 시간 스케일링 기능 구현
  - 실시간(1x) 및 가속(10~100x) 시뮬레이션 모드
  - 시간 스케일 동적 조정
  - 가속 모드에서의 물리 모델 정확성 유지
  - 적응형 시간 제어 및 물리 정확도 모니터링
  - 전역 시간 스케일러 및 GUI 통합 지원
  - _Requirements: 4.6_

- [x] 8.2 데이터 로깅 및 분석 도구
  - 시계열 데이터 저장 (SQLite 기반)
  - 성능 분석 도구 (온도 안정성, 냉각 효율, 가동률, 알람 빈도)
  - 트렌드 분석 및 예측 (다항식 피팅 기반)
  - 한국어 분석 리포트 생성 (일일 리포트, 권장사항)
  - pandas/numpy 기반 고급 분석 기능
  - _Requirements: 7.5_

- [x] 8.3 AI 에이전트 연동 도구
  - tools/agent_cli.py 구현 (완전한 CLI 인터페이스)
  - Kiro AI agent 통신 클라이언트
  - 자동 시나리오 생성 (고장, 성능 테스트)
  - 지능형 진단 및 최적화 제안 (한국어 지원)
  - 배치 처리 및 자동화 스크립트 지원
  - _Requirements: 7.1_

- [x] 8.4 원격 제어 인터페이스
  - FastAPI 기반 REST API 구현
  - WebSocket 실시간 통신
  - 웹 기반 대시보드 (한국어 지원)
  - 원격 모니터링 및 제어 (센서 조회, 명령 실행, 알람 관리)
  - 데이터 내보내기 (JSON/CSV 형식)
  - 보안 및 인증 지원 준비
  - _Requirements: 7.2_