# contract_analyzer — ios_sim 백엔드 레퍼런스 앱

진짜 iPhone 시뮬레이터(iOS 26)에서 9:41 status bar · Dynamic Island · 시스템 한글 키보드까지 포함해 캡처하는 예제. `dark_studio` preset으로 3컷 콜라주가 떨어진다.

## 한 번에 돌리기

```bash
xcrun simctl shutdown all                       # 시뮬 깨끗하게
rm -rf shotgun_output shotgun_output_composed
shotgun capture && shotgun compose && shotgun compose-grid
open shotgun_output_composed/_grid.png          # ← 결과
```

첫 실행은 시뮬 부팅 + flutter build로 ~3분. 이후 재실행은 ~30초.

## 결과물

- `shotgun_output/ios/6.7/ko/{01_list,02_detail,03_search}.png` — 원본 캡처 (각 ~250KB)
- `shotgun_output_composed/_grid.png` — 3-phone 콜라주, 스토어 업로드용

`03_search.png`에 한글 두벌식 키보드가 들어와 있으면 성공.

## 핵심 셋업 (다른 앱에 적용할 때)

| 파일 | 무엇이 들어가야 하나 |
|---|---|
| `ios/Runner/Info.plist` | `CFBundleURLTypes`에 `shotgun` scheme 등록 |
| `lib/main.dart` | `_DeeplinkRouter` 패턴 — `AppLinks().uriLinkStream` 리스너에서 `popUntil(isFirst)` + `addPostFrameCallback`으로 `pushNamed` |
| `shotgun.yaml` | `advanced.backend: ios_sim`, scene별 `pre_capture: [{action: keyboard_show}, {action: wait, ms: 300}]` |

자세한 건 [docs/PHASE2.md](../../docs/PHASE2.md) 참조.

## 트러블슈팅

- **`03_search.png`에 키보드가 없다** → macOS Privacy & Security → Accessibility에서 터미널(또는 Claude Code)을 허용. AppleScript로 시뮬 메뉴를 클릭하는 데 권한 필요.
- **"Open in App?" 다이얼로그가 캡처에 들어간다** → 같은 권한 문제. AppleScript Return 키스트로크가 막혀 있음.
- **빌드가 30분 넘게 멈춰있다** → `flutter clean && cd ios && pod install`.
