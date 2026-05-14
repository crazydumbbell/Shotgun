# tasks/lessons.md

자기개선용 레슨 — 같은 실수 반복하지 않도록 누적.

## 2026-05-13

### codegen은 사용자 코드의 가시성 가정을 깨면 안 됨
- **레슨**: Dart는 `export ... show X`로 심볼을 재노출하지만, 이를 import한 쪽에서 그 심볼이 보이게 하는 동작은 코드 생성기가 자동으로 처리해주지 않는다. 사용자가 main.dart에서 MyApp을 re-export만 하면 생성된 테스트의 `const MyApp()`는 "Couldn't find constructor"로 죽는다.
- **규칙**: 사용자 입력으로 받은 심볼이 import하려는 파일에 실제로 선언되어 있는지 *사전 검사*하라. 안 되어 있으면 Dart 컴파일러 에러를 그대로 노출하지 말고, 명시적인 우회 옵션(`root_widget_import` 등)을 가리키는 한국어 한 줄 메시지로 ValueError를 던져라.

### main() 우회는 디폴트가 아닌 명시적 선택이어야 함
- **레슨**: integration_test에서 root widget을 직접 pump하면 사용자 `main()` 안의 `dotenv.load()` / `MobileAds.initialize()` / `Firebase.initializeApp()`가 전부 스킵된다. 첫 화면이 이 globals를 읽으면 즉시 NotInitializedError로 폭발.
- **규칙**: 사용자가 부트스트랩 훅을 등록할 수 있는 명시적 옵션 (`bootstrap_fn` 같은 것)을 제공하고, README/CONFIG_SCHEMA에서 "shotgun은 당신 앱의 main()을 호출하지 않는다"를 굵게 강조하라. 이는 한 번 당하면 한 시간 잡아먹는 함정.

### subprocess는 그냥 흘려보내면 노이즈가 사용자 시야를 덮음
- **레슨**: macOS의 "Failed to foreground app", pdfx 같은 패키지의 deprecation 경고는 캡처 자체에는 무해하지만, cold build 한 번이면 100+줄 노이즈를 만들어 실제 shotgun 출력이 묻힌다.
- **규칙**: subprocess.run으로 그냥 흘리지 말고 `Popen + 라인 스트리밍 + 화이트리스트 필터`를 기본값으로. `--verbose`로 켤 수 있게. 단, 진짜 에러(`EXCEPTION CAUGHT`, `Couldn't find`, `Error:`)는 절대 화이트리스트에 추가하지 말 것.

### 실패는 한 줄로 먼저 요약하라
- **레슨**: Flutter widget tree 에러는 800+ 프레임짜리 raw stack을 토해낸다. 사용자 입장에서는 "어떤 shot, 어떤 widget, 무엇이 실패했나"가 stack frame 0번이 아닌 그 위 framework preamble 한 줄에 있다.
- **규칙**: subprocess 출력을 스트리밍 파싱해서 (a) 실패한 shot ID (`+N -1 : <id> [E]` 라인)와 (b) 첫 framework error 라인(`#0` stack frame은 스킵)을 골라 종료 직전 stderr에 한 줄로 출력. raw stack은 그대로 유지 — 요약은 *추가*이지 *대체*가 아님.

## 2026-05-15

### `flutter run` 위의 백엔드에서 locale을 강제하는 유일한 합리적 경로는 `--dart-define` + 앱-쪽 어댑터
- **레슨**: macos_host 백엔드는 `flutter test` 위에서 돌아서 `tester.platformDispatcher.localesTestValue`를 강제할 수 있지만, ios_sim 백엔드는 `flutter run`이라 test binding이 없다. simctl로 `defaults write -g AppleLanguages '("ko")'` + 시뮬 재부팅 (~45초)도 가능하지만, 사용자 앱이 이미 `flutter_localizations` 세팅돼 있다면 `--dart-define=SHOTGUN_LOCALE=<lang>` + `MaterialApp.locale: ShotgunLocale.fromEnv()` 한 줄이 훨씬 싸다 (incremental rebuild ~10-15s vs. 부팅 ~45s).
- **규칙**: 시뮬레이터 백엔드에서 locale 같은 "앱이 시작 전에 알아야 하는" 값을 주입할 때는 (a) 사용자 앱에 1줄 어댑터를 두고 (b) shotgun이 dart-define으로 값을 넘기는 패턴이 디폴트. 시스템-레벨 우회는 사용자가 앱 수정을 명시적으로 거부할 때만 추가.

### dart-define으로 locale을 바꾸려면 flutter run을 재시작해야 한다
- **레슨**: `String.fromEnvironment(...)`는 컴파일타임 상수. hot-restart는 dart-define을 재평가하지 않는다 — 이미 인라이닝된 상수를 들고 다닌다. 그래서 locale 그룹을 inner loop로 두면 시각적으로는 바뀌지 않는다 (silent bug).
- **규칙**: 컴파일타임 dart-define로 주입하는 값은 매 변경마다 프로세스 재시작이 필수. 루프 구조는 항상 (device → locale → scenes) — locale이 outer-of-flutter-run, scene은 cheap deeplinks로 inner. 반대로 두면 매 scene마다 ~10-15s 재빌드가 곱해진다.

### 사용자 dart_defines와 shotgun-관리 키가 충돌할 때 shotgun 값이 이긴다
- **레슨**: 사용자가 yaml의 `app.dart_defines`에 `SHOTGUN_LOCALE`을 직접 적어두면(실수든 의도든), `{**user, **shotgun_managed}` 순서가 아니면 shotgun의 per-locale 루프 값이 사용자 값으로 덮여서 매 컷이 같은 locale로 렌더된다 (silent no-op).
- **규칙**: dart_defines 같은 dict를 머지할 때, shotgun-관리 키가 **마지막에** 들어가도록. 단위 테스트에 사용자가 키를 미리 설정한 케이스(`SHOTGUN_LOCALE=fr`)를 명시적으로 잠가둘 것.

### iOS 시뮬레이터의 software keyboard input source는 app locale과 별개
- **레슨**: `MaterialApp.locale = en`으로 영어 UI를 캡처해도, `keyboard_show`로 뜨는 시스템 키보드는 시뮬레이터의 **시스템 input source** (Settings → General → Keyboard → Keyboards)를 따른다. ko/en을 둘 다 캡처한 contract_analyzer 검증에서 en search 페이지 본문은 영어로 잘 렌더됐지만 키보드는 한글 두벌식이 그대로 떴음.
- **규칙**: locale-별로 키보드 종류가 다르게 보여야 하는 사용자(예: en은 QWERTY, ko는 두벌식)는 PR-C.3에서 `keyboard_locale` 액션을 추가하거나, 사용자가 시뮬에 미리 두 input source를 등록하고 shotgun이 globe 키 누름을 자동화하는 방향. 지금은 PR-C.2 범위 밖 — 별도 작업 항목으로 남길 것. **(PR-C.3에서 `keyboard_locale` 액션으로 구현 완료 — Ctrl-Space로 다음 source 토글)**

### 길이가 다른 리스트끼리 슬라이스 비교는 silent no-match
- **레슨**: 테스트 mock에서 `if cmd[:3] == ["xcrun", "simctl"]:` 분기를 썼다가 항상 False로 빠짐. `cmd[:3]`는 길이 3, 비교 대상은 길이 2 → 절대 같지 않다. mock의 captured dict가 비어 있는데 테스트 실패 메시지는 `KeyError: 'cmd'`로만 나와서 1차원적으로는 "왜 호출이 안 됐지?"로 보임.
- **규칙**: 슬라이스로 prefix 매칭을 할 땐 슬라이스 길이와 비교 리터럴 길이를 반드시 일치. 또는 `cmd[0] == "xcrun" and cmd[1] == "simctl"`처럼 인덱스 비교가 명료. 테스트 작성 시 mock이 expected 분기에 실제로 들어갔는지 한 번은 print로 확인할 것 — `captured` 사전이 비었으면 단언이 KeyError로 죽지만 그게 진짜 원인 신호가 아님.

### simctl-driven UI 액션은 best-effort, 사용자 권한 누락 시 silently swallow
- **레슨**: `keyboard_show` / `keyboard_locale` / `share_sheet`는 osascript로 Simulator의 menu / globe key / button을 누른다. 셋 다 macOS Accessibility 권한이 필요해서 CI나 새 환경에서는 실패 가능. 이걸 raise하면 매트릭스 전체가 죽고, 다른 정상 scene 캡처까지 날아간다.
- **규칙**: simctl push 같은 권한-불필요 호출은 정상 에러로 raise(자료 누락 등). 반대로 osascript 의존 호출은 `try / except (FileNotFoundError, subprocess.TimeoutExpired): pass`로 일관 swallow. 부분 실패는 스크린샷에 UI 상태가 빠진 형태로 남고, 사용자가 그걸 보고 권한 부여하면 됨 — 매트릭스 전체를 막을 일이 아니다.
