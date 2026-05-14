# shotgun — 현재 상태 (handoff)

작성: 2026-05-15 (PR-C.2 완료). 새 채팅에서 이 파일만 읽어도 어디까지 했고 다음에 뭘 할지 파악 가능하도록.

---

## 한 줄 요약

Phase 1 + 1.5 + 실사용자 피드백 4건 + 목업 품질 업그레이드 4건 + **Phase 2 PR-A/B (실제 iOS Simulator backend MVP)** + **PR-C.1 (`pre_capture` DSL — keyboard_show / wait, 시스템 한글 키보드 캡처)** + **PR-C.2 완료 (multi-locale via `--dart-define=SHOTGUN_LOCALE` + `ShotgunLocale.fromEnv()` adapter)** 까지. `shotgun init / capture / compose / compose-grid` 풀 파이프라인이 `shotgun.yaml` 한 장으로 돌아가고, 사실적 device frame (CC0 PommePlate) · 5종 compose preset (`vivid_gradient` / `minimal` / `feature_callout` / `studio` / `dark_studio`) · multi-phone 콜라주 · declarative router hook · iOS status bar normalize · `macos_host` ↔ `ios_sim` 백엔드 분리. notes_app 매트릭스 12/12 회귀 없음 + Python 단위테스트 **38/38** (PR-C.2에서 ios_sim backend 테스트 6개 추가) + contract_analyzer가 진짜 iOS 26.4 시뮬레이터(iPhone 17 Pro Max)에서 9:41/Dynamic Island 포함 **en/ko 2-locale × 3-scene = 6컷** 캡처 성공 (en은 "My contracts / Residential lease...", ko는 "내 계약서 / 주거용 임대차계약서...").

---

## 다음 채팅에서 이어갈 때 (HANDOFF — 2026-05-15, PR-C.2 완료)

### PR-C.2 — ios_sim multi-locale ✅ 완료

**한 줄**: `--dart-define=SHOTGUN_LOCALE=<lang>` + `ShotgunLocale.fromEnv()` 한 줄 어댑터. ios_sim 백엔드는 locale마다 `flutter run`을 재시작 (cold ~30s, 이후 incremental ~10-15s). contract_analyzer에서 en/ko 6컷 캡처 검증 성공 — en은 영어 UI, ko는 한국어 UI, 같은 레이아웃 같은 위치에 정확히 분기.

**완료된 것 (워킹트리에 미커밋):**
- `packages/shotgun_cli/src/shotgun_cli/backends/ios_sim.py` — `_capture_one_device`가 이제 (device → locale → scenes) 3단계. 새 헬퍼 `_capture_one_locale`이 한 (device, locale) 페어마다 `flutter run` 라이프사이클을 담당. single-locale guard 제거.
- `_start_flutter_run`에 `extra_dart_defines: dict[str, str] | None` 파라미터 추가. shotgun-관리 키가 사용자 키를 덮어쓰도록 머지 순서 `{**user, **shotgun_managed}`.
- `packages/shotgun_cli/tests/test_ios_sim_backend.py` (신규, 6 tests) — subprocess.run / subprocess.Popen / time.sleep / _screenshot 전부 monkeypatch. 잠가둔 contract: locale마다 flutter run 1회, 매 invocation에 `SHOTGUN_LOCALE=<lang>` 포함, user dart_defines 머지 보존, 사용자가 `SHOTGUN_LOCALE`을 직접 설정했을 때 shotgun이 덮어씀, single-locale 회귀 없음.
- `examples/contract_analyzer/lib/main.dart` — `import shotgun_runner`, `MaterialApp.locale: ShotgunLocale.fromEnv()` 한 줄, 핵심 헤더/카드/SectionLabel/SummaryCard/RiskBanner 텍스트를 `_tr(context, ko:, en:)` 헬퍼로 분기.
- `examples/contract_analyzer/pubspec.yaml` — `shotgun_runner`를 dev_dependencies → dependencies로 이동 (production main.dart import).
- `examples/contract_analyzer/shotgun.yaml` — `locales: [en, ko]`, scene마다 en 캡션 추가.
- `README.md` — "ios_sim에서 multi-locale 쓰기" 서브섹션. `docs/PHASE2.md` — "Locale switching" 섹션 재작성 (B 옵션 결정 트레일 + 왜 system-level/deeplink 거절했나).

**검증 결과 (2026-05-15):**
- `shotgun_output/ios/6.7/{en,ko}/{01_list,02_detail,03_search}.png` 6장 모두 생성 (byte size 다름 = 실제 다른 콘텐츠 렌더링).
- en/01_list.png: "My contracts / 5 analyzed in the last 7 days / Residential lease / Freelance services..." 정상 영어 렌더링.
- ko/01_list.png: "내 계약서 / 최근 7일 동안 분석한 5건 / 주거용 임대차계약서 / 프리랜서 용역계약서..." 정상 한국어 렌더링.
- pytest 38/38 green (기존 32 + ios_sim backend 신규 6).

**알려진 후속 (PR-C.3 후보):**
- iOS 시뮬레이터의 software keyboard **input source** (한글 두벌식 vs QWERTY)는 app locale과 별개. en 캡처에서도 키보드는 한글로 떴음. locale-별 키보드 렌더링이 필요하면 PR-C.3에서 `keyboard_locale` 액션 추가하거나 사용자가 시뮬 input source 두 개 등록 후 globe-key 자동화 검토.

### 결정 트레일 (이미 확정된 것, 흔들지 말 것)

- **A(system-level AppleLanguages) vs B(dart-define) vs C(하이브리드)**: B 확정. 사유: locale-당 부팅 ~45s 비용 회피, 사용자 앱 1줄 추가만으로 됨. 한 줄 수정 거부 사용자가 나타나면 그때 A 추가.
- **locale 그룹 vs scene 그룹 (outer)**: locale 그룹 outer. 사유: `--dart-define`은 compile-time 상수라 `flutter run` 재시작 없이는 못 바꿈. 매 scene마다 재시작은 ~10-15s × N 곱하기 디스아스터.
- **flutter run 재시작 vs hot-restart**: 재시작. hot-restart는 dart-define을 재평가하지 않음.
- **runner 헬퍼 위치**: 별도 파일 `src/shotgun_locale.dart`. `shotgun_capture.dart`에 안 합침 — Localizations 책임 분리, import 가벼움.

### 다음 작업 우선순위

1. **PR-C.2 commit**: 사용자가 git commit 지시하면 단일 커밋. 변경 파일은 위 "완료된 것" 섹션 그대로. WIP 커밋 0174a74 위에 squash가 깨끗할지, 별도 commit이 깨끗할지는 사용자 판단.
2. **PR-C.3 — 추가 액션**: `share_sheet`, `notification`. `share_sheet`는 share 버튼 selector를 yaml에 받아서 AppleScript click. `notification`은 `simctl push` 1회. `keyboard_locale` 액션은 위 "후속" 항목 — 우선순위는 사용자 요구 봐서.
3. **PR-D**: Android emulator 백엔드 (adb + emulator -avd + screencap). iOS-sim의 mirror 구조.

### 그 이전 (HANDOFF — 2026-05-14, PR-C.1 완료)

PR-C.1 — `pre_capture` DSL ✅ 완료

**한 줄**: `keyboard_show` + `wait` 액션을 yaml에 추가하고, AppleScript로 Simulator의 `I/O → Keyboard → Toggle Software Keyboard` 메뉴를 클릭해서 software 키보드가 실제로 화면에 뜨도록 함. 3컷 캡처 + 콜라주 + pytest 32/32 모두 통과.

**완료된 것:**
- `SceneConfig.pre_capture: list[dict]` 추가 + validator (`config.py:135-176`). 액션 `keyboard_show` / `wait` 화이트리스트, 알 수 없는 액션은 load time에 거부.
- `IosSimBackend._dispatch_action()` (`backends/ios_sim.py`). `wait`는 `ms` 만큼 sleep, `keyboard_show`는 software keyboard 토글 + 0.6s dwell.
- **핵심 발견**: `defaults write com.apple.iphonesimulator ConnectHardwareKeyboard -bool false`는 **이미 실행 중인 Simulator GUI 세션에서는 무효**. 부팅 전에 호출해도 동일 — Simulator GUI는 앱 launch 시점에만 이 pref를 읽는다. 대신 `osascript`로 `I/O → Keyboard → Toggle Software Keyboard` 메뉴(Cmd-K)를 클릭하는 게 신뢰할 수 있는 유일한 방법. `_toggle_software_keyboard()` 헬퍼로 구현 — osascript/Accessibility 권한 없으면 swallow.
- contract_analyzer에 `ContractSearchPage` 추가 — autofocus TextField + 최근 검색어 + 추천 키워드 chips.
- `_DeeplinkRouter._handleUri` 수정: `popUntil(isFirst)` + `addPostFrameCallback`으로 push 지연 → search route 정상 진입.
- shotgun.yaml에 search scene + `pre_capture: [keyboard_show, wait 300ms]` 추가.

**검증 결과 (2026-05-14):**
- `shotgun_output/ios/6.7/ko/03_search.png` 220KB — 화면 하단에 시스템 한글 두벌식 키보드 + ✓ 보내기 버튼 + 마이크 + 지구본 + 이모지 모두 보임.
- `shotgun_output/ios/6.7/ko/{01_list,02_detail}.png` 회귀 없음 (각 280KB, 301KB).
- `shotgun_output_composed/_grid.png` — 3-phone 콜라주에 ±5° 회전 + dark_studio preset + 한글 캡션.
- `pytest packages/shotgun_cli` 32/32 green.

**남은 작업 (다음 채팅 우선순위):**
1. **PR-C.1 commit**: 사용자가 git commit 지시하면 단일 커밋으로. 변경 파일:
   - `packages/shotgun_cli/src/shotgun_cli/config.py` (pre_capture validator)
   - `packages/shotgun_cli/src/shotgun_cli/backends/ios_sim.py` (`_dispatch_action`, `_toggle_software_keyboard`, hw keyboard toggle)
   - `examples/contract_analyzer/lib/main.dart` (`_DeeplinkRouter`, `ContractSearchPage`)
   - `examples/contract_analyzer/shotgun.yaml` (search scene)
   - `docs/STATUS.md`, `docs/PHASE2.md`
2. **PR-C.2 시작**: multi-locale. System-level `AppleLanguages` 스위칭 vs deeplink query param(`?locale=ko`) 둘 다 지원할지 결정. 사용자 앱 변경 최소화 관점에선 system-level이 깔끔.
3. **PR-C.3**: `share_sheet`, `notification` 액션. `share_sheet`는 share 버튼 selector를 yaml에 받아서 AppleScript click. `notification`은 `simctl push` 1회.
4. **PR-D**: Android emulator 백엔드 (adb + emulator -avd + screencap). 사실상 iOS-sim의 mirror 구조.

### Phase 2 전체 진행도

- ✅ **PR-A**: 백엔드 ABC 추출 (`backends/{base,macos_host}.py` + `capture.py` dispatcher) — 동작 변화 0
- ✅ **PR-B**: iOS sim 백엔드 MVP — boot/status_bar/deeplink/screenshot/teardown
- ✅ **PR-C.1**: `pre_capture` DSL (`keyboard_show` + `wait`) — 검증 완료
- ✅ **PR-C.2**: multi-locale (`--dart-define=SHOTGUN_LOCALE` + `ShotgunLocale.fromEnv()` adapter) — en/ko end-to-end 검증 완료
- ⬜ **PR-C.3**: 추가 액션 (`share_sheet`, `notification`, 후보: `keyboard_locale`)
- ⬜ **PR-D**: Android emulator 백엔드 (adb + emulator -avd + screencap)

### 알려진 trickiness (PR-C 이어갈 때 주의)

1. **iOS "Open in App?" confirm dialog**: 백엔드가 첫 prime openurl + AppleScript Return으로 dismiss. 두 번째부터 OS가 다이얼로그 생략. AppleScript는 Accessibility 권한 필요 — CI에서 안 됨 (PR-D 작업하면서 같이 해결할 일).
2. **`pushNamed`가 deeplink listener에서 즉시 호출되면 NavigatorState rebuild와 race**. `addPostFrameCallback`으로 한 프레임 미루는 게 필수 (`main.dart:_handleUri`).
3. **iOS 시뮬레이터는 `--release` / `--profile` 미지원** (no JIT-less runtime). 백엔드는 `flutter run` (debug) 사용. 빌드는 첫 번째만 ~30s, 이후 즉시.
4. **software keyboard 강제 표시는 AppleScript 메뉴 클릭만 신뢰 가능**. `defaults write ConnectHardwareKeyboard false`는 Simulator GUI에서 무시됨. `_toggle_software_keyboard()`는 토글이라 idempotent하지 않음 — 두 번째 `keyboard_show`가 같은 세션에서 호출되면 키보드를 *내릴* 수 있다. 한 매트릭스에 search scene을 두 개 두면 두 번째가 키보드 없이 캡처될 가능성. PR-C.2/.3에서 명시적 `keyboard_hide` 액션 추가하거나 메뉴 항목의 mark/checked 상태 검사로 idempotent하게 만드는 것 검토.
5. **AppleScript는 Accessibility 권한 필요**. macOS Privacy & Security → Accessibility → Terminal/iTerm/Claude Code 허용. CI에선 불가 → `_toggle_software_keyboard()`는 best-effort, 실패하면 키보드 없이 캡처되지만 다른 신은 정상.
6. **dPR 자동 스케일** (`examples/contract_analyzer/lib/main.dart`의 `_s` getter): 시뮬레이터 dPR > 1.5면 1.0, macOS host dPR=1.0이면 2.2. 새 예제 만들 때 같은 패턴 따를 것.

---

## 지금 동작하는 것

### CLI

```bash
shotgun init                  # ./shotgun.yaml 스타터 생성
shotgun capture               # → integration_test/_shotgun_generated.dart codegen
                              #   → entitlements <true/> → <false/> 자동 패치
                              #   → flutter test -d macos 실행
                              #   → entitlements 원상복구
                              #   → shotgun_output/<platform>/<device>/<locale>/NN_<scene>.png
shotgun compose               # → shotgun_output_composed/... 매트릭스 컴포지트
shotgun compose <raw> <out>   # 단일 이미지 모드 (yaml 없을 때)
shotgun compose-grid          # → shotgun_output_composed/_grid.png (멀티-phone 콜라주)
```

### 검증된 매트릭스 — examples/notes_app/

```
2 devices × 2 locales × 3 scenes = 12 shots
└─ 12/12 통과, ~8초/pass (cold build 후)
└─ en/ko PNG byte size 다름 → locale switching 작동
└─ Korean 캡션 깨끗하게 렌더 (tofu 버그 해결)
└─ /, /note/1, /search 라우트 navigation 작동
```

raw 결과: `examples/notes_app/shotgun_output/`
컴포지트 결과: `examples/notes_app/shotgun_output_composed/`

---

## 레포 구조

```
Flutter_Mocup_Maker/
├── README.md                      # 프로젝트 인트로
├── docs/
│   ├── ARCHITECTURE.md            # 두 패키지 분리 이유, 파이프라인
│   ├── CONFIG_SCHEMA.md           # shotgun.yaml 풀 스펙
│   ├── ROADMAP.md                 # Phase 1/2/3
│   ├── SPIKES.md                  # 스파이크 + Phase 1 / 1.5 진입 로그
│   └── STATUS.md                  # ← 이 파일
├── .github/workflows/ci.yml       # pytest + flutter analyze + capture smoke
├── packages/
│   ├── shotgun_runner/            # Dart, pub.dev 대상
│   │   └── lib/src/shotgun_capture.dart   # + ShotgunRouterHandler
│   └── shotgun_cli/               # Python, PyPI 대상
│       ├── src/shotgun_cli/
│       │   ├── __init__.py
│       │   ├── cli.py             # click entrypoint (init/capture/compose)
│       │   ├── config.py          # Pydantic ShotgunConfig + iter_matrix()
│       │   ├── codegen.py         # Jinja2 → _shotgun_generated.dart
│       │   ├── entitlements.py    # macOS sandbox 자동 패치 + self-heal
│       │   ├── capture.py         # codegen → entitlements → flutter test
│       │   └── compose.py         # Pillow + presets + platform-aware fonts
│       └── tests/                 # pytest 18 cases (config/codegen/compose)
├── examples/
│   ├── counter_app/               # 단일 route 데모 (Flutter default counter)
│   │   └── shotgun.yaml
│   └── notes_app/                 # 3-route 노트 앱 (Phase 1.5)
│       ├── shotgun.yaml           # + advanced.status_bar.normalize, app.setup_file
│       ├── lib/main.dart          # MyApp + HomePage + NoteDetailPage + SearchPage
│       ├── integration_test/_shotgun_setup.dart   # router hook 등록 데모
│       └── pubspec.yaml           # flutter_localizations 포함
├── presets/                       # 비어있음 (Phase 2에서 채울 자리)
├── spike/                         # 초기 spike 코드 (참고용 보관)
└── .venv/                         # python venv, shotgun_cli editable 설치됨
```

---

## 핵심 API

### shotgun_runner (Dart)

`ShotgunCapture` — 모두 static. 일반적으로 codegen이 호출하지만 직접 작성한 통합 테스트에서도 쓸 수 있음.

| 메서드 | 역할 |
| --- | --- |
| `framedApp(Widget)` | `RepaintBoundary` + `GlobalKey`로 사용자 root 위젯을 감쌈. 캡처 가능한 subtree로 만듦 |
| `setLocale(tester, lang)` | `tester.platformDispatcher.locale[s]TestValue` 설정. **pumpWidget 전에 호출** |
| `resizeFor(tester, device)` | `setSurfaceSize` + `tester.view.physicalSize` + `devicePixelRatio = 1.0`. **pumpWidget 전** |
| `setRouterHandler(handler?)` | declarative router 앱용 hook. 등록 시 `navigateTo`가 hook 호출, 미등록 시 Navigator pushNamed fallback. handler 내부에서 `pushNamed`를 await하면 hang — `unawaited(...)` 또는 `GoRouter.of(ctx).go(...)` 같은 fire-and-forget API 사용 |
| `navigateTo(tester, route)` | hook 우선, 없으면 root `Navigator.pushNamed`. `'/'`은 no-op. **pumpAndSettle 후** |
| `capture(device, sceneId, locale?, fileName?)` | `boundary.toImage` → PNG → `SHOTGUN_OUT_DIR/<platform>/<device>/<locale>/<fileName>.png` |

`ShotgunDevice` — `{platform, name, width, height}`. width/height는 double.
`ShotgunRouterHandler` — `Future<void> Function(WidgetTester, String route)`.

### shotgun_cli (Python)

- `config.ShotgunConfig.model_validate(dict)` — Pydantic 검증 (preset 이름·locale별 caption coverage 등)
- `config.iter_matrix() → list[ShotMatrixEntry]` — (device, locale, scene) 펼침 + `scenes[].only` 필터링
- `codegen.write_integration_test(config, project_root) → Path` — Jinja2 렌더 후 파일 쓰기. `app.setup_file` 지정 시 setup import + `main()` 첫줄에서 호출 주입
- `entitlements.sandbox_disabled(project_root)` — context manager. 진입 시 stale `.shotgun-bak` 자동 복원(self-heal), finally에서 원본 복원
- `capture.run_capture(config, project_root, ...)` — 풀 오케스트레이션
- `compose.compose(screenshot_path, output_path, caption, preset, *, status_bar=None) → Path` — Pillow 컴포지트
- `compose.preset_by_name(name) → Preset` — `vivid_gradient`, `minimal`, `feature_callout`
- `compose.StatusBarOptions(enabled, time, style, color)` — iOS shot에 9:41/배터리 stamp 옵션

---

## codegen 동작 모델

`integration_test/_shotgun_generated.dart`이 매번 생성됨 (`--keep-generated` 없으면 capture 끝나고 삭제). 한 `testWidgets` 블록 per shot:

```dart
ShotgunCapture.setLocale(tester, shot.locale);
await ShotgunCapture.resizeFor(tester, device);
await tester.pumpWidget(ShotgunCapture.framedApp(const MyApp()));
await tester.pumpAndSettle();
await ShotgunCapture.navigateTo(tester, shot.route);
await ShotgunCapture.capture(
  device: device,
  locale: shot.locale,
  sceneId: shot.sceneId,
  fileName: '${shot.index.toString().padLeft(2, '0')}_${shot.sceneId}',
);
```

핵심 결정:
- `MaterialApp`은 사용자 앱이 가지고 있음. codegen은 `Localizations`를 감싸지 않음 — 작동 안 함 (MaterialApp이 자기 거로 덮어씀).
- 대신 `setLocale`로 `PlatformDispatcher` 레벨에서 강제.
- multi-scene은 기본적으로 `Navigator.pushNamed` (`MaterialApp.routes` / `onGenerateRoute` 가정). declarative router (`go_router`, `auto_route`, `beamer` 등) 앱은 `app.setup_file`에 setup hook을 두고 `ShotgunCapture.setRouterHandler(...)`로 라우팅을 위임 — codegen이 setup 파일을 import하고 `main()`에서 setup 함수 호출.
- `app.setup_file`은 `integration_test/` (상대경로 import) 또는 `lib/` (`package:<app>/...` import) 아래여야 함.

---

## 사용자가 자기 앱에 적용할 때 필요한 것 (notes_app이 모범)

1. `pubspec.yaml`에 `shotgun_runner: { path: ... }` 추가 (배포 후엔 pub.dev 버전)
2. multi-locale을 쓸 거면 `flutter_localizations` + `GlobalMaterialLocalizations.delegate` 등 명시 + `MaterialApp.supportedLocales` 명시
3. 라우팅: (a) `MaterialApp.routes` / `onGenerateRoute`면 자동 동작. (b) `go_router` 등 declarative router는 `integration_test/_shotgun_setup.dart`에 `shotgunSetup()`을 두고 안에서 `ShotgunCapture.setRouterHandler(...)` 등록 + `shotgun.yaml`의 `app.setup_file` 지정.
4. macOS 빌드 디렉토리에 `macos/Runner/DebugProfile.entitlements` 있어야 함 (shotgun이 자동 패치, 죽어도 self-heal)
5. iOS status bar normalize 원하면 `advanced.status_bar.normalize: true`. 사용자 앱이 상단 ~44pt SafeArea를 비워둬야 stamp가 겹치지 않음.
6. `shotgun init && shotgun capture && shotgun compose`

---

## 알려진 한계 / 다음에 해결할 것

### 짧게 손볼 것 — 모두 완료
- ✅ README 갱신 (설치, 빠른 시작, 폰트/locale 셋업 노트)
- ✅ counter_app 옛 `composed_output/` 잔재 정리
- ✅ `.gitignore`에 `_shotgun_generated.dart`, `shotgun_output*/`, `composed_output/`, `*.shotgun-bak` 명시
- ✅ `entitlements.py` self-heal: 이전 실행이 Ctrl-C로 죽었을 때 `.shotgun-bak`을 다음 실행에서 복원

### 중간 크기 — 모두 완료
- ✅ **declarative router hook**: `ShotgunCapture.setRouterHandler(...)`로 go_router/auto_route/beamer 사용 앱 지원. 사용자는 `app.setup_file` 옵션으로 hook을 등록 (`integration_test/_shotgun_setup.dart`). 미등록 시 기존 Navigator pushNamed fallback.
- ✅ **Linux/CI 폰트 경로**: macOS/Linux/Windows 후보군 각각 분리, 현재 OS 우선으로 머지. `SHOTGUN_FONT_LATIN/KO/CJK` 환경변수로 override 가능. 모든 후보 실패 시 stderr에 경고 한 번.
- ✅ **추가 preset**: `vivid_gradient`(기본), `minimal`(흰 배경+다크 캡션), `feature_callout`(vivid + ring + arrow). `lifestyle`은 배경 이미지 자산이 필요해 보류.
- ✅ **status bar normalization**: `advanced.status_bar.normalize: true` 활성화 시 iOS shot에만 9:41 + 100% 배터리 stamp. raw screenshot → phone framing 사이에 적용. style=auto는 상단 픽셀 밝기로 텍스트 색 자동 결정.
- ✅ **CI 워크플로**: `.github/workflows/ci.yml`. (1) Ubuntu에서 `shotgun_cli` pytest 18건, (2) 두 example의 `flutter analyze`, (3) macOS-14에서 notes_app full capture+compose smoke + 12개 PNG 검증 + artifact 업로드.

### 실사용자 피드백 (2026-05-13) — 모두 완료
- ✅ **root_widget이 export로 재노출된 경우 빌드 실패**: codegen이 `app.entry` 파일에 `class <root_widget>` 선언이 있는지 미리 검사. 없으면 Dart 컴파일러 에러("Couldn't find constructor 'MyApp'") 대신 `app.root_widget_import: 'package:<pkg>/app.dart'`로 명시하라는 메시지를 ValueError로 던짐. 사용자가 직접 import 경로를 지정하면 그대로 신뢰.
- ✅ **main() 부트스트랩 누락**: `app.bootstrap_fn` (setup_file의 async 함수명) 옵션 추가. 각 `testWidgets` 본문에서 `pumpWidget` 전에 `await _shotgun_setup.<fn>()` 호출. 사용자는 `dotenv.load()` / `MobileAds.initialize()` / `Firebase.initializeApp()`를 거기 모아두면 됨. `bootstrap_fn`만 설정하고 `setup_file`이 비면 Pydantic 단계에서 거부.
- ✅ **캡처 로그 노이즈**: macOS의 `Failed to foreground app`, pdfx류 `scanHexInt32 deprecated` 등 알려진 무해 경고를 `_BENIGN_LINE_SUBSTRINGS`로 분류하고 기본 숨김. `shotgun capture -v / --verbose`로 켤 수 있음. 실제 에러(`EXCEPTION CAUGHT`, `Couldn't find` 등)는 절대 숨기지 않음.
- ✅ **실패 시 1줄 요약**: capture가 subprocess 출력을 스트리밍하면서 `+N -1 : ios/6.7/en/home [E]` 같은 라인을 잡아 어떤 shot에서 죽었는지 추적하고, 그 뒤 ~수십줄에서 raw stack frame을 제외한 첫 framework 에러 라인을 picks. 종료 시 stderr에 `[shotgun] failed at ios/6.7/en/home — NotInitializedError ...` 한 줄 + 기존 raw stack도 그대로 남김.

### 목업 품질 업그레이드 (2026-05-13) — 모두 완료
- ✅ **사실적 device frame**: PommePlate(CC0)에서 iPhone XS Max/11 Pro Max + SE 2nd gen PNG 3개를 `packages/shotgun_cli/src/shotgun_cli/assets/devices/`에 동봉. `_FRAME_REGISTRY`에 inner screen rect 하드코딩 (스캔 헬퍼로 측정). `PhoneConfig.frame_id` 기본값 `"iphone_notch_space_gray"`. frame PNG 로드 시 screen rect를 알파 0으로 punch-out → 그 자리에 screenshot이 보이고, frame은 베젤/노치/유리 하이라이트만 위에 덮음. `frame_id=None`이면 기존 synthetic bezel 경로(`_render_phone_synthetic`)로 fallback.
- ✅ **`studio` preset**: 오프화이트 배경 + phone 위, 캡션 phone 아래에 작게. 마그니픽 lookbook 스타일. `compose()`에 캡션 below 분기 (`top_ratio > 0.5`이면 phone을 위에 놓고 캡션을 phone 아래에 anchor).
- ✅ **shadow / caption 톤다운**: `vivid_gradient`의 shadow_blur 90→130, shadow_opacity 120→75, caption stroke_opacity 60→30, max_height_ratio 0.18→0.13. minimal도 비슷하게 다시 튜닝. 캡션이 더 이상 화면을 짓누르지 않음.
- ✅ **`shotgun compose-grid`**: 매트릭스의 composed PNG를 자동 수집해 4-column 콜라주 한 장으로 출력 (`_grid.png`). 각 phone에 고정 시퀀스 회전 ±5°와 cast shadow. `--cols`, `-o`, `--locale` 옵션. 출력 재현성 보장(랜덤 시드 없음).
- ✅ **자산 패키징**: `pyproject.toml`의 `[tool.setuptools.package-data]`에 `shotgun_cli.assets.devices`. `importlib.resources`로 로드해서 editable/wheel/sdist 모두에서 동작.

### 큰 것 (Phase 2)
- pub.dev / PyPI 첫 배포
- README에 실제 GIF 데모
- 첫 외부 사용자 onboarding 문서
- `lifestyle` preset (배경 이미지 위에 phone) — 자산 큐레이션 필요
- Golden-image visual regression (현재 unit test는 shape 검증만)
- Declarative router 통합 시나리오를 진짜로 검증하는 별도 example (예: `examples/notes_app_gorouter/`)

---

## 개발 환경 메모

- Flutter 3.41.9, Dart 3.11.5, Pillow 12.2.0, Python 3.10+
- `.venv` 활성화: `source /Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/activate`
- 또는 직접: `/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/shotgun ...`
- 캡처는 macOS desktop (`flutter test -d macos`) 위에서만 돌아감. iOS/Android 시뮬레이터 안 씀
- 첫 빌드 ~2분, incremental ~8초

---

## 자주 보는 명령

```bash
# notes_app에서 풀 사이클 다시 돌리기
cd examples/notes_app
rm -rf shotgun_output shotgun_output_composed
/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/shotgun capture
/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/shotgun compose

# Python 단위테스트 (18 cases)
/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/pytest \
  /Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/packages/shotgun_cli

# codegen 결과만 dry-run으로 확인
/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/python -c "
from pathlib import Path
from shotgun_cli.config import load_config
from shotgun_cli.codegen import render_integration_test
cfg = load_config(Path('shotgun.yaml'))
print(render_integration_test(cfg, Path('.')))
"

# 단일 preset 빠른 시각 확인
/Users/exchip/Desktop/exchip/Flutter_Mocup_Maker/.venv/bin/shotgun compose \
  shotgun_output/ios/6.7/en/01_home.png /tmp/out.png --preset minimal

# entitlements 상태 확인
grep -A1 "app-sandbox" macos/Runner/DebugProfile.entitlements
```

---

## 새 채팅에서 시작할 때

1. 이 파일 + `docs/PHASE2.md` 읽기 (선택: `docs/SPIKES.md`, `docs/ROADMAP.md`)
2. **PR-C.2 multi-locale 작업 재개** — 위 "진행 중: PR-C.2" 섹션의 "남은 작업" 1~7번 순서대로. 워킹트리에 `shotgun_locale.dart` + `shotgun_runner.dart` 두 파일 변경분이 미커밋 상태로 남아있음 (`git status`로 확인). 설계 결정(B 옵션)은 이미 확정 — 흔들지 말고 그대로 진행.
3. 회귀 빠른 확인 (Phase 1 macos_host): `pytest packages/shotgun_cli` + `cd examples/notes_app && shotgun capture && shotgun compose`
4. 회귀 빠른 확인 (Phase 2 ios_sim): `cd examples/contract_analyzer && xcrun simctl shutdown all && rm -rf shotgun_output* && shotgun capture && shotgun compose && shotgun compose-grid` — `shotgun_output/ios/6.7/ko/03_search.png`에 시스템 키보드 있는지 확인
