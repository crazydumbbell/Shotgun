# shotgun

> App Store / Play Store 스크린샷을 Flutter 프로젝트에서 자동으로 만들어주는 도구.

Flutter 앱을 다 만들었는데 스토어 등록용 스크린샷 수백 장(아이폰 6.7"·6.5"·아이패드·안드로이드 폰·태블릿 × 모든 언어)을 일일이 찍어야 한다? `shotgun.yaml` 한 장 쓰고 명령어 세 번 치면 끝.

```bash
shotgun init       # shotgun.yaml 생성
shotgun capture    # 앱을 자동 실행해서 화면 캡처
shotgun compose    # 그라데이션 배경 + 폰 프레임 + 자막 합성
```

결과물:

```
shotgun_output_composed/
  ios/6.7/en/01_home.png   ← 스토어에 그대로 업로드 가능
  ios/6.7/ko/01_home.png
  android/phone/en/01_home.png
  ...
```

---

## 시작하기 전에 확인할 것

- [ ] **macOS** 쓰고 있나요? (캡처는 `flutter test -d macos`로 돌아갑니다. Windows/Linux는 아직 미지원)
- [ ] Flutter **3.41+**, Python **3.10+** 설치돼 있나요?
- [ ] 본인 Flutter 앱이 **macOS 빌드 설정**이 돼 있나요? (`macos/` 폴더가 있고 `flutter run -d macos`가 한 번이라도 성공했어야 함)

세 개 다 OK면 아래 5분 만에 끝납니다.

---

## 5분 셋업 — VSCode에서 본인 Flutter 프로젝트만 열려있는 상태에서

### 1. shotgun CLI 설치 (한 번만)

VSCode 터미널 열고 (`Ctrl+`` ` 또는 Cmd+J):

```bash
python3 -m venv ~/.shotgun-venv
source ~/.shotgun-venv/bin/activate
pip install "git+https://github.com/crazydumbbell/Shotgun.git#subdirectory=packages/shotgun_cli"
shotgun --help
```

마지막 줄이 도움말을 보여주면 성공.

> 다음 번에 터미널 새로 열었을 때 `shotgun` 명령어가 안 보이면 `source ~/.shotgun-venv/bin/activate` 한 번 다시 실행. 매번 치기 싫으면 `~/.zshrc`에 그 줄 추가하거나 [pipx](https://pipx.pypa.io/)로 설치하면 됨.

### 2. 본인 Flutter 앱에 shotgun_runner 추가

VSCode 좌측 파일트리에서 `pubspec.yaml` 열고, `dev_dependencies:` 아래에 추가:

```yaml
dev_dependencies:
  flutter_test:
    sdk: flutter

  # 아래 두 개 추가 ↓
  shotgun_runner:
    git:
      url: https://github.com/crazydumbbell/Shotgun.git
      path: packages/shotgun_runner
      ref: main
  integration_test:
    sdk: flutter
```

저장하고 터미널에서:

```bash
flutter pub get
```

### 3. shotgun.yaml 만들기

```bash
shotgun init
```

`shotgun.yaml`이 프로젝트 루트에 생깁니다. VSCode에서 열어서 본인 앱에 맞게 수정:

```yaml
app:
  entry: lib/main.dart
  root_widget: MyApp           # 본인 앱의 root 위젯 이름

devices:
  ios:
    - { name: "6.7", size: [1290, 2796] }    # 아이폰 15 Pro Max
  android:
    - { name: "phone", size: [1080, 1920] }

locales: [en, ko]

theme:
  preset: vivid_gradient        # vivid_gradient | minimal | feature_callout

scenes:
  - id: home
    route: /                    # 본인 앱의 라우트 이름
    caption:
      en: "Every thought,\nin one place"
      ko: "모든 생각을\n한곳에"
```

> `root_widget`은 `runApp(MyApp())`에서 `MyApp` 부분. `scenes`의 `route`는 `MaterialApp(routes: { ... })`에 등록한 경로. 라우트가 없으면 `/` 하나만 적어도 OK.

### 4. 실행

```bash
shotgun capture && shotgun compose
```

- **capture**: 본인 앱을 macOS desktop으로 자동 실행해서 각 scene을 PNG로 저장. 첫 빌드는 ~2분, 그 다음부터는 한 컷에 ~8초.
- **compose**: 그 PNG에 그라데이션 + 폰 프레임 + 캡션 입혀서 스토어 업로드용 이미지로 변환.

```bash
open shotgun_output_composed/
```

Finder가 열리면 끝.

---

## 한국어/일본어 자막은요?

`locales: [en, ko, ja]`라고 적고 각 scene에 해당 언어 caption만 추가하면 됩니다. shotgun이 알아서 locale을 전환하면서 캡처해요.

**조건 두 개:**

1. 본인 앱이 `flutter_localizations`를 쓰고 `MaterialApp.supportedLocales`에 해당 언어가 들어 있어야 함.
2. macOS는 한글/한자 폰트가 기본 설치돼 있어서 그냥 됨. 다른 OS(CI 등)에서는 [Localization 가이드](#cjk-폰트-linux--ci) 참고.

자막이 `▯▯▯` (두부)로 나오면 폰트 문제 — 첫 `shotgun compose` 실행 시 stderr에 경고가 찍힙니다.

---

## 자주 막히는 곳

<details>
<summary><strong>"<code>MyApp</code> not found" 같은 에러</strong></summary>

`shotgun.yaml`의 `root_widget`이 본인 앱의 실제 root 위젯 이름과 정확히 같아야 합니다. `lib/main.dart`의 `runApp(...)` 안에 있는 클래스 이름 확인하세요.
</details>

<details>
<summary><strong><code>flutter test -d macos</code>에서 멈춰있음</strong></summary>

- `macos/Runner/DebugProfile.entitlements` 파일이 있어야 합니다. 없으면 `flutter create --platforms=macos .`로 macOS 지원 추가.
- `go_router` 같은 declarative router를 쓰면 별도 셋업이 필요해요 → [docs/ROADMAP.md](docs/ROADMAP.md)의 router hook 섹션.
</details>

<details>
<summary><strong>스크린샷이 비어있거나 검은색</strong></summary>

- `MaterialApp` 하나만 root에 있어야 합니다. `MaterialApp` 안에 또 `MaterialApp`을 두면 locale이 안 먹어요.
- `route`가 본인 앱의 routes 맵에 실제로 등록돼 있는지 확인.
</details>

<details>
<summary><strong>Ctrl+C로 중간에 끊었더니 앱이 이상함</strong></summary>

shotgun이 캡처하는 동안 macOS 샌드박스를 잠시 끄는데, Ctrl+C로 끊겨도 다음 실행 때 자동 복원돼요. 수동으로 복원하려면:

```bash
mv macos/Runner/DebugProfile.entitlements.shotgun-bak \
   macos/Runner/DebugProfile.entitlements
```
</details>

<details>
<summary><strong>CJK 폰트 (Linux / CI)</strong></summary>

```bash
# Ubuntu
sudo apt-get install fonts-noto-cjk

# 또는 직접 지정
export SHOTGUN_FONT_KO=/path/to/Pretendard-Bold.otf
```
</details>

그 외엔 [이슈](https://github.com/crazydumbbell/Shotgun/issues) 남겨주세요.

---

## 진짜 시뮬레이터에서 찍고 싶다 (ios_sim 백엔드)

기본 백엔드(macos_host)는 Flutter 위젯 트리만 캡처해서 빠르지만 — 시스템 키보드, 진짜 status bar, share sheet는 못 찍는다. 그게 필요하면 ios_sim 백엔드:

```yaml
# shotgun.yaml
advanced:
  backend: ios_sim
  scheme: shotgun            # ios/Runner/Info.plist에 등록할 URL scheme

scenes:
  - id: search
    route: /search
    pre_capture:             # 캡처 직전에 실행할 액션
      - { action: keyboard_show }
      - { action: wait, ms: 300 }
```

결과: `xcrun simctl io` 실제 시뮬 framebuffer 캡처. 9:41 status bar, Dynamic Island, 시스템 키보드 다 들어옴. 한 컷에 ~5–8초 (Phase 1 macos_host의 ~8초와 비슷, 부팅 한 번에 ~45초 추가).

레퍼런스 앱: [examples/contract_analyzer](examples/contract_analyzer) — `shotgun capture && shotgun compose-grid` 한 번이면 3-phone 콜라주 PNG가 떨어진다.

> AppleScript로 시뮬 메뉴를 클릭하는 데 macOS Accessibility 권한이 필요. System Settings → Privacy & Security → Accessibility에서 터미널 허용.

---

## 더 알아보기

- [docs/CONFIG_SCHEMA.md](docs/CONFIG_SCHEMA.md) — `shotgun.yaml` 전체 옵션 (status bar normalize, scene 필터링, preset 커스터마이즈 등)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 동작 원리 (codegen → entitlements 패치 → flutter test → Pillow 합성)
- [docs/PHASE2.md](docs/PHASE2.md) — ios_sim 백엔드 설계와 `pre_capture` DSL 레퍼런스
- [docs/ROADMAP.md](docs/ROADMAP.md) — 앞으로 들어올 것 (Android emulator, pub.dev 배포, GIF 데모)
- [docs/STATUS.md](docs/STATUS.md) — 현재 어디까지 됐는지
- [examples/notes_app](examples/notes_app) — macos_host 백엔드 레퍼런스 (다국어 3-route)
- [examples/contract_analyzer](examples/contract_analyzer) — ios_sim 백엔드 레퍼런스 (한글 키보드 포함)

---

## 기여

이슈/PR 환영합니다. 특히 도움 되는 것:

- **실제 앱에 써보고 막힌 부분 리포트** — 지금 단계에서 가장 가치 있음
- **새 compose preset** — `packages/shotgun_cli/src/shotgun_cli/compose.py`에 추가
- **declarative router 통합 예제** (`go_router`, `auto_route`)

개발 셋업:

```bash
git clone https://github.com/crazydumbbell/Shotgun.git
cd Shotgun
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/shotgun_cli[dev]"
pytest packages/shotgun_cli       # 단위 테스트 18개
```

---

## License

[MIT](LICENSE).
