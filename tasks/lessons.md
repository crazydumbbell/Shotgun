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
