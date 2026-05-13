# tasks/todo.md

## 2026-05-13 — 실사용자 피드백 4건

- [x] **#1 root_widget export 재노출 지원**
  - [x] `AppConfig.root_widget_import` 옵션 추가 + Pydantic shape 검증
  - [x] codegen `_resolve_root_widget_import` — 명시 import 우선, 없으면 `lib/<entry>`에서 `class <root_widget>` 선언 사전 검사
  - [x] entry에 선언이 없으면 `root_widget_import` 안내 메시지로 `ValueError`
  - [x] 테스트: override 존중 / 미선언 시 raise / 직접 선언 시 통과
- [x] **#2 main() 부트스트랩 누락**
  - [x] `AppConfig.bootstrap_fn` 옵션 추가, `setup_file` 없이는 거부
  - [x] codegen 템플릿: `testWidgets` 본문에서 `pumpWidget` 전에 `await _shotgun_setup.<fn>()`
  - [x] 테스트: 호출이 setLocale 전에 emit되는지 / setup_file 없이 거부되는지
- [x] **#3 캡처 로그 노이즈 필터**
  - [x] `_BENIGN_LINE_SUBSTRINGS` 화이트리스트 (Failed to foreground app, scanHexInt32, prototype warning)
  - [x] `subprocess.Popen` 스트리밍으로 라인별 필터링
  - [x] `shotgun capture -v / --verbose` 플래그
  - [x] 테스트: 무해 패턴 매칭 / 진짜 에러 통과
- [x] **#4 실패 시 1줄 요약**
  - [x] `_FailureContext` — `+N -1 : <id> [E]` 패턴으로 shot id 캡쳐, 이후 라인에서 framework error preamble을 root cause로 선택 (stack frame은 스킵)
  - [x] CaptureError 메시지 + stderr `[shotgun]` 한 줄 요약
  - [x] 테스트: shot id+cause 포함 / 컨텍스트 비면 None / 긴 라인 trim

## Review

- 4건 모두 코드 + 테스트 + CONFIG_SCHEMA.md + STATUS.md "실사용자 피드백" 섹션 반영.
- 회귀 위험 큰 곳은 codegen 템플릿 변경 (entry import → `root_widget_import` 변수화). 기존 example(notes_app, counter_app) 둘 다 `class MyApp`을 entry에 직접 선언하고 있어 preflight 통과 → 거동 동일.
- 다음 사용자 onboarding 시점에 README "Apply to your app" 절에 `bootstrap_fn` 사용례 + dotenv 예제 추가하면 좋음 (별도 todo).
