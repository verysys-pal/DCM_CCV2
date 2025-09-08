# DCM Cryo Cooler 시뮬레이터 작업 목록

> 목적: Reference 폴더의 자료를 반영하여 EPICS 기반 Cryo Cooler 제어로직 시뮬레이터(IOC + GUI + 테스트 하네스)를 단계적으로 구현/검증한다.

## 0) 준비 및 기준 합의
- [ ] 개발 언어/도구 확정: Python 3.10+, EPICS Base 7.x, CSS Phoebus
- [ ] 실행 환경 점검: softIoc, SNCSEQ, phoebus, pyepics/p4p 설치 확인
- [ ] PV 네이밍 규칙 확정(Reference_Guide.md 6.1) 및 공유
- [ ] 최소 수용 기준(각 단계의 완료 정의, Acceptance Criteria) 합의

## 1) 시뮬레이터 코어 (Reference 7)
- [x] 폴더 스캐폴딩: `sim/core`, `sim/cli`, `sim/tests`
- [x] 열용량/1차지연 모델 `CryoPlant` 초안 구현 (`step(Tsp, Qload, dt)`)
- [x] 간단 제어기(PI 또는 bang-bang) 임시 구현 `_controller(Tsp)`
- [x] 시간 전개 루프와 샘플링 주기(예: 10 Hz) 결정/적용
- [x] CLI 실행기: setpoint/부하 입력 → 현재 온도/상태 출력
- [x] 단위 테스트: 모델 수렴/안정성 기본 검증
  - 수용 기준: 일정 시간 내 `|T − Tsp| < 10K` 유지(Guide 9.3 예시)

## 2) EPICS IOC (Reference 6)
- [x] DB 스켈레톤 추가: `db/dcm_cryo.db` (Guide 6.3 발췌 반영)
- [x] SNL 초안 추가: `ioc/snl/dcm_cryo.stt` (Guide 6.4 기반 상태 전이)
- [x] `st.cmd` 수정: DB 로드, SNL 빌드/로드, 심볼릭 PV 연결
- [x] 빌드/실행 스크립트: softIoc 로컬 기동/정지 스크립트 작성
- [x] 상태→PV 매핑: `STATE:MAIN`, `CMD:MAIN`, 주요 AI/AO 연결
  - 수용 기준: 로컬에서 softIoc 기동, 주요 PV `caget/caput` 정상 동작

## 3) 데이터 연동
- [x] 시뮬레이터 ↔ IOC 연동 방식 결정: (a) p4p/pyepics로 주기 업데이트, (b) SNL/stream/asyn 드라이버 중 택1
- [x] (임시) Python publisher: `BL:DCM:CRYO:TEMP:COLDHEAD` 등 주기 업데이트
- [x] 명령 경로: `CMD:MAIN` caput → 시뮬레이터 상태 반영(or SNL에서 구동)
  - 수용 기준: `SETPOINT` 변경 시 Coldhead 온도 추종, 상태 전이 가시화

## 4) CSS Phoebus GUI (Reference 8, gui/*)
- [ ] 기존 `gui/bob/main.bob`, `synoptic.bob` PV 바인딩 점검/정합화
- [ ] 알람/상태/트렌드 위젯 연결 및 단위(EGU) 표시 정리
- [ ] 실행 문서화: `phoebus -resource gui/bob/main.bob`
  - 수용 기준: 주요 PV 실시간 표시, 상태/알람 위젯 정상 표시

## 5) 시험용 프로그램 (Reference 9)
- [x] 의존성 파일 추가: `requirements.txt` (pyepics/p4p/pytest/hypothesis/rich)
- [x] 시나리오 러너: `tests/tools/runner.py` (plan yaml 구동)
- [x] 기본 시나리오: `tests/scenarios/normal_start.yaml` 생성
- [x] 이상 시나리오: `tests/scenarios/flow_loss.yaml` 생성
- [ ] 프로퍼티 테스트: 가열/냉각 오차, 알람 불변식 테스트 작성
  - 수용 기준: 정상/이상 시나리오 통과, 기본 프로퍼티 테스트 성공

## 6) 문서/운영 절차 (Reference 10, 13)
- [ ] README 보강: 전체 구조/실행 방법/트러블슈팅 요약
- [ ] 운전 절차 체크리스트: 정상/비정상/회복 절차 가이드
- [ ] 알람/인터락 표 정리 및 Ack 흐름 설명

## 7) 품질/자동화
- [ ] Make 타깃/스크립트: `make ioc`, `make sim`, `make run`, `make test`
- [ ] 포맷터/린터(선택): `ruff/black` (코어/툴만 대상)
- [ ] (옵션) CI 구성 초안: 로컬 pre-commit 수준에서 대체 가능

---

## 참고/출처
- `Reference/Reference_Guide.md`의 6,7,8,9,10,13 절 요구사항을 우선 반영
- `gui/bob/*.bob` 현행 파일과 PV 매핑 유지/보완
- EPICS 레코드/상태기계는 SoftIOC + SNL 기준으로 최소 구성 후 확장

## 다음 단계 제안
1) 1)~2) 범위 구현부터 시작: 코어/IOC 스켈레톤 생성
2) 3) 임시 Python 연동으로 빠른 가시화
3) 4) GUI 연결 확인 → 5) 시나리오/테스트 도입
