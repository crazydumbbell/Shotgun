# shotgun — 현재 상태 (handoff)

작성: 2026-05-13 (updated). 새 채팅에서 이 파일만 읽어도 어디까지 했고 다음에 뭘 할지 파악 가능하도록.

---

## 한 줄 요약

Phase 1 + 1.5 + 실사용자 피드백 4건 + 목업 품질 업그레이드 4건 모두 완료. `shotgun init / capture / compose / compose-grid` 풀 파이프라인이 `shotgun.yaml` 한 장으로 돌아가고, 사실적 device frame (CC0 PommePlate) · 4종 compose preset (`vivid_gradient` / `minimal` / `feature_callout` / `studio`) · multi-phone 콜라주 · declarative router hook · iOS status bar normalize까지 들어옴. notes_app 매트릭스 12/12 회귀 없음 + Python 단위테스트 32/32. 다음은 Phase 2 (pub.dev/PyPI 배포, GIF 데모, golden-image visual regression, Android frame).

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

1. 이 파일 + `docs/SPIKES.md` + `docs/ROADMAP.md` 읽기
2. 사용자가 새 방향 던지지 않으면, "큰 것 (Phase 2)"의 첫 항목 제안 — 우선순위 추천: (a) golden-image visual regression (현재 unit test는 shape만 검증, 진짜 시각 회귀는 못 잡음), (b) pub.dev / PyPI 첫 배포 준비, (c) declarative router 통합 example
3. 회귀 빠른 확인: `pytest packages/shotgun_cli` + `cd examples/notes_app && shotgun capture && shotgun compose`
