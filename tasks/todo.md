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

## 2026-05-15 — PR-C.2 ios_sim multi-locale

- [x] **ios_sim 백엔드 (device → locale → scenes) 3단계 그룹핑** + 새 헬퍼 `_capture_one_locale`
- [x] **single-locale guard 제거** (`backends/ios_sim.py`)
- [x] **`_start_flutter_run`에 `extra_dart_defines` 추가** + `{**user, **shotgun_managed}` 머지 순서
- [x] **`tests/test_ios_sim_backend.py` 신규 (6 tests)** — subprocess mock으로 locale 루프/dart-define/머지/단일 locale 회귀 모두 잠금
- [x] **README + PHASE2.md 갱신** — `ShotgunLocale.fromEnv()` 한 줄 가이드, Locale switching 섹션 재작성 (B 옵션 결정 트레일)
- [x] **contract_analyzer 와이어링** — `MaterialApp.locale: ShotgunLocale.fromEnv()`, `_tr()` 헬퍼로 헤더/카드/SectionLabel/SummaryCard/RiskBanner 분기, shotgun.yaml `locales: [en, ko]` + en 캡션 추가, shotgun_runner를 dev → prod dep으로 이동
- [x] **end-to-end 검증** — `shotgun capture`로 en/ko 6컷 PNG 생성, byte size 다름, en/ko 본문 텍스트 정상 분기 (육안 확인)
- [x] **lessons.md 갱신** — dart-define + 앱 어댑터 패턴 / flutter run 재시작 필수 / 머지 순서 / 시스템 키보드 input source는 별개

## Review (PR-C.2)

- pytest 38/38 (32 + 6 신규) green.
- en/01_list.png: "My contracts / Residential lease..." 정상 영어 렌더, ko/01_list.png: "내 계약서 / 주거용 임대차계약서..." 정상 한국어 렌더, 같은 레이아웃 동일 위치.
- 관찰된 후속: en 모드의 software 키보드가 한글 두벌식으로 떴음 (시스템 input source는 app locale과 별개). PR-C.3 `keyboard_locale` 액션 후보로 lessons.md / STATUS.md에 기록.
- 워킹트리에 미커밋 변경분 — 사용자가 commit 지시하면 단일 커밋으로 squash. WIP 커밋 0174a74 위에 별도 커밋이 명료할 듯.

## 2026-05-15 — PR-C.3 extra pre_capture 액션

- [x] **`pre_capture` whitelist 확장** — `config.py`에서 `notification` / `keyboard_locale` / `share_sheet` 추가, 각 액션마다 required keys 집합으로 검증, payload mapping / target string 타입 가드까지
- [x] **`_dispatch_action` 확장** — 세 branch + 모듈-레벨 헬퍼 3개 (`_push_notification` tempfile + simctl push / `_press_globe_key` Ctrl-Space osascript / `_tap_accessibility_button` quote-escaping). dispatcher 시그니처에 `udid` 추가
- [x] **단위 테스트 9개 추가** — `test_config.py`에 validator 5건, `test_ios_sim_backend.py`에 dispatcher 4건. 47/47 green
- [x] **CONFIG_SCHEMA.md** — "pre_capture actions" 섹션 + 전체 액션 레퍼런스 표 + 권한 노트
- [x] **PHASE2.md** PR-C.3 ✅ DONE 마킹 + 구현 디테일

## Review (PR-C.3)

- 모든 신규 액션이 best-effort posture (osascript / FileNotFound / Timeout silently swallow). 같은 `keyboard_show` 패턴 따름 — 부분 실패가 매트릭스 전체를 죽이지 않음.
- 첫 작성한 dispatcher 테스트에서 `cmd[:3] == ["xcrun", "simctl"]` 길이 mismatch 버그를 잡았음. 길이 2짜리 리스트를 길이 3 슬라이스와 비교하면 항상 False → 사일런트 no-match. 다른 테스트 헬퍼에 같은 패턴이 없는지 grep으로 확인 완료.
- end-to-end 시뮬 검증은 의도적으로 스킵 — 단위 테스트가 cmd shape / payload / AppleScript embedding을 정확히 잠갔고, 시뮬 동작 자체는 simctl push / Ctrl-Space / accessibility click 모두 Apple 문서화된 표면. contract_analyzer에서 실제 마케팅 PNG가 필요할 때 자연스럽게 검증될 부분.
- 워킹트리 미커밋 — 사용자가 commit 지시하면 단일 커밋으로.

## 2026-05-15 — PR-D Android emulator 백엔드 (Phase 2 마지막 PR)

- [x] **`AndroidEmuBackend` 신규** — `backends/android_emu.py`. ios_sim 구조 mirror: `_capture_one_device` → `_capture_one_locale` → per-scene `am start -W -d shotgun://<route> <package>`. SystemUI demo-mode broadcasts로 status bar 9:41/100%/4-bar. screencap을 bytes로 받아 PNG 디스크 라이트.
- [x] **SDK 도구 resolver** — `_sdk_root()` / `_adb_bin()` / `_emulator_bin()`: ANDROID_HOME → `~/Library/Android/sdk` → PATH 폴백.
- [x] **이미 부팅된 에뮬레이터 재사용** — `_running_emulator_serial()`로 `emulator-*` 시리얼 발견 시 재부팅 스킵. 개발 루프 ~30s 절약.
- [x] **`AppConfig.package_id` 추가** — Android applicationId. android_emu에서만 lazy 검증 (`run()` 진입부에서 missing이면 CaptureError).
- [x] **`_VALID_BACKENDS`에 android_emu 추가** + backends/__init__.py에 등록.
- [x] **단위 테스트 11개** — `tests/test_android_emu_backend.py`. screencap의 bytes 모드(`subprocess.run` capture_output without text=True)와 일반 텍스트 모드를 라우팅 fake로 분기. multi-locale 루프, dart-define 주입+머지+충돌 시 shotgun 승리, am start URL/package, demo-mode enter/exit 1쌍, package_id/emu_avd missing/unknown reject, 미구현 액션 silent skip+stderr, wait 액션 동작.
- [x] **example/contract_analyzer에 Android 타겟** — `flutter create --platforms android .`로 android/ 디렉토리 생성, `AndroidManifest.xml`에 `shotgun://` URL scheme intent-filter 추가, `shotgun.yaml`에 commented android device block + `package_id`. boilerplate `test/widget_test.dart` 제거 (잘못된 MyApp 참조).
- [x] **README + CONFIG_SCHEMA.md + PHASE2.md + STATUS.md + lessons.md 갱신**.

## Review (PR-D)

- pytest 58/58 (47 + 11 신규) green.
- end-to-end Android 실기 캡처는 의도적으로 미수행 — 본 머신에 등록된 AVD 없음. 단위 테스트가 cmd shape / multi-locale 흐름 / demo-mode pairing / 친절 에러 메시지까지 정확히 잠갔으니 첫 실사용자가 AVD 등록 + `shotgun capture` 한 방이면 자연스럽게 검증될 부분.
- `flutter analyze` on contract_analyzer 깨끗 (boilerplate test 제거 후 No issues).
- **Phase 2 완료** — 세 백엔드(macos_host / ios_sim / android_emu) 모두 동작, 같은 yaml로 분기 가능.

## 2026-05-15 — PR-E.1 배포 준비 (pub.dev / PyPI)

- [x] **shotgun_runner pubspec.yaml 보강** — 0.0.1 → 0.1.0, description 다듬기, `homepage` / `repository` / `issue_tracker` / `documentation`, `topics: [screenshot, integration-test, app-store, localization, testing]`
- [x] **shotgun_runner LICENSE / CHANGELOG.md / README.md** — pub.dev 점수 항목 충족. README는 quick install + multi-locale 예제 + go_router 예제 + 링크 구조로 재작성
- [x] **flutter pub publish --dry-run PASS** — 워킹트리 변경분 1 warning만 (커밋 후 사라짐, publish 차단 아님)
- [x] **shotgun_cli pyproject.toml 보강** — 0.0.1 → 0.1.0, description 한 줄→풀, keywords 추가 (ios-simulator, android-emulator, integration-test, localization), classifiers 보강 (Development Status :: 4 - Beta, Python 3.10–3.13, MacOS / Linux OS, Topic :: Multimedia :: Graphics + Testing), project URLs 추가 (Issues / Documentation / Changelog), optional-dependencies dev에 build / twine 추가
- [x] **shotgun_cli LICENSE / CHANGELOG.md / README.md** — README는 quick install + 백엔드 선택 + capabilities 목록 + 링크 구조로 재작성
- [x] **python -m build + twine check PASSED** — sdist (`shotgun_cli-0.1.0.tar.gz`) + wheel (`shotgun_cli-0.1.0-py3-none-any.whl`) 둘 다 통과. android_emu / ios_sim / macos_host / assets / tests 모두 포함
- [x] **루트 README.md** — install 안내에 "곧 PyPI / pub.dev" 병기. publish 후 본격 전환

## Review (PR-E.1)

- 실제 publish는 사용자 pub.dev / PyPI 계정 OAuth 필요 — 본 세션에서 진행 불가. dry-run + twine check로 publish 직전까지 완료.
- pyproject의 trove classifier `Development Status :: 4 - Beta`로 변경 (Phase 2 완료된 시점이라 Pre-Alpha 아님).
- shotgun_cli wheel은 6KB가 아닌 wheel 본체에 모든 코드 + CC0 PommePlate device frame PNG 3개 + tests를 포함. 첫 publish 후 wheel size 확인 필요 (몇 MB일 수 있음).

## 2026-05-15 — Android end-to-end 검증 ⚠️ 부분

- [x] AVD 등록 여부 재확인 — `emulator -list-avds` 빈 출력. 본 머신에 AVD 없음.
- [ ] **사용자 작업 필요**: Android Studio → Tools → Device Manager → Create Device → 시스템 이미지 다운로드 (~1GB+). 시스템 이미지 다운로드는 자동화 부적절.
- [ ] AVD 등록 후 `cd examples/contract_analyzer && shotgun capture` 한 번이면 PR-D 표면 실기 검증 완료. 정상 작동 시 STATUS.md의 "Android end-to-end" 섹션을 ✅로 전환.
