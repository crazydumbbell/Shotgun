import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:shotgun_runner/shotgun_runner.dart';

final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();

void main() {
  runApp(const ContractAnalyzerApp());
}

/// Listens for `shotgun://<route>` deeplinks (the URL scheme registered
/// in Info.plist / AndroidManifest.xml) and forwards them to the
/// MaterialApp navigator. Used by shotgun's ios_sim backend to drive
/// scene-by-scene navigation via `xcrun simctl openurl`.
class _DeeplinkRouter extends StatefulWidget {
  const _DeeplinkRouter({required this.child});
  final Widget child;

  @override
  State<_DeeplinkRouter> createState() => _DeeplinkRouterState();
}

class _DeeplinkRouterState extends State<_DeeplinkRouter> {
  late final AppLinks _appLinks;
  StreamSubscription<Uri>? _sub;

  @override
  void initState() {
    super.initState();
    _appLinks = AppLinks();
    _sub = _appLinks.uriLinkStream.listen(_handleUri);
    // Also handle a cold-start deeplink (the simulator launches the app
    // and then openurl fires; either could win the race).
    _appLinks.getInitialLink().then((uri) {
      if (uri != null) _handleUri(uri);
    });
  }

  void _handleUri(Uri uri) {
    // shotgun://contract/1  →  route '/contract/1'
    // shotgun://            →  route '/'
    final path = uri.path.isEmpty
        ? (uri.host.isEmpty ? '/' : '/${uri.host}')
        : '/${uri.host}${uri.path}'.replaceAll('//', '/');
    final route = path.isEmpty ? '/' : path;
    debugPrint('[shotgun-app] deeplink ${uri.toString()} → $route');
    final nav = _navKey.currentState;
    if (nav == null) {
      debugPrint('[shotgun-app] navigator not ready');
      return;
    }
    // First pop any stacked routes so we always start from root, then
    // push the target. Two separate calls keep behavior obvious — we
    // saw pushNamedAndRemoveUntil quietly collapse the result on some
    // routes in earlier testing.
    nav.popUntil((r) => r.isFirst);
    if (route != '/') {
      // Defer the push by one frame so popUntil's stack mutation is
      // fully applied before pushNamed runs.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        nav.pushNamed(route);
        debugPrint('[shotgun-app] pushed $route');
      });
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// Pick a string for the active locale. We don't pull in `intl` /
/// `flutter_localizations` codegen since the marketing screenshot
/// example only needs two languages and a handful of headers. Anything
/// the user sees first (page titles, section labels, the most prominent
/// list items) lives here; the long-tail body text stays Korean.
String _tr(BuildContext context, {required String ko, required String en}) {
  return Localizations.localeOf(context).languageCode == 'en' ? en : ko;
}

const _bgColor = Color(0xFFF7F4EE);
const _cardColor = Colors.white;
const _ink = Color(0xFF1B1B1F);
const _muted = Color(0xFF6B6B73);
const _riskHigh = Color(0xFFE25D5D);
const _riskMid = Color(0xFFE6A23C);
const _riskLow = Color(0xFF5BAA67);

// Phase 1 macos_host backend runs at 1290×2796 logical px with
// devicePixelRatio=1.0 — values that look right on a real 430pt-wide
// iPhone need ~2.2× scaling to fill that canvas. On real hardware or
// iOS Simulator (Phase 2 ios_sim backend) the dPR is ~3.0 and logical
// width is ~430pt, so _s collapses to 1.0 and the same numbers render
// at their natural sizes.
double get _s {
  final view =
      WidgetsBinding.instance.platformDispatcher.views.first;
  // dPR > 1.5 ≈ real device / simulator → no scaling needed.
  return view.devicePixelRatio > 1.5 ? 1.0 : 2.2;
}

class ContractAnalyzerApp extends StatelessWidget {
  const ContractAnalyzerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return _DeeplinkRouter(
      child: MaterialApp(
        navigatorKey: _navKey,
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: _bgColor,
          colorScheme: ColorScheme.fromSeed(
            seedColor: _riskHigh,
            brightness: Brightness.light,
          ).copyWith(surface: _bgColor),
          textTheme: const TextTheme().apply(
            bodyColor: _ink,
            displayColor: _ink,
          ),
        ),
        locale: ShotgunLocale.fromEnv(),
        supportedLocales: const [Locale('ko'), Locale('en')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        initialRoute: '/',
        routes: {
          '/': (_) => const ContractListPage(),
          '/contract/1': (_) => const ContractDetailPage(),
          '/search': (_) => const ContractSearchPage(),
        },
      ),
    );
  }
}

// Reserve the iOS status-bar zone shotgun stamps 9:41 / battery into.
// We need this since shotgun runs without real device insets.
const double _statusBarReserve = 100;

// ─────────────────────────────────────────────────────────
// List — "내 계약서"
// ─────────────────────────────────────────────────────────
class ContractListPage extends StatelessWidget {
  const ContractListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ListView(
        padding: EdgeInsets.fromLTRB(
          24 * _s, _statusBarReserve + 20 * _s, 24 * _s, 60 * _s,
        ),
        children: [
          Text(
            _tr(context, ko: '내 계약서', en: 'My contracts'),
            style: TextStyle(
              fontSize: 34 * _s,
              fontWeight: FontWeight.w800,
              color: _ink,
              letterSpacing: -0.5,
              height: 1.0,
            ),
          ),
          SizedBox(height: 6 * _s),
          Text(
            _tr(
              context,
              ko: '최근 7일 동안 분석한 5건',
              en: '5 analyzed in the last 7 days',
            ),
            style: TextStyle(fontSize: 15 * _s, color: _muted),
          ),
          SizedBox(height: 22 * _s),
          const _SummaryCard(),
          SizedBox(height: 28 * _s),
          _SectionLabel(_tr(context, ko: '최근 분석', en: 'Recent')),
          SizedBox(height: 12 * _s),
          _ContractCard(
            title: _tr(context, ko: '주거용 임대차계약서', en: 'Residential lease'),
            party: _tr(
              context,
              ko: '강남구 역삼동 · 김민준',
              en: 'Gangnam-gu Yeoksam · Minjun Kim',
            ),
            date: _tr(context, ko: '오늘', en: 'Today'),
            risk: _Risk.high,
            riskLabel: _tr(context, ko: '위험 4건', en: '4 risks'),
          ),
          SizedBox(height: 14 * _s),
          _ContractCard(
            title: _tr(
              context,
              ko: '프리랜서 용역계약서',
              en: 'Freelance services',
            ),
            party: _tr(
              context,
              ko: '에이전시 · 박지윤',
              en: 'Agency · Jiyun Park',
            ),
            date: _tr(context, ko: '어제', en: 'Yesterday'),
            risk: _Risk.mid,
            riskLabel: _tr(context, ko: '주의 2건', en: '2 to review'),
          ),
          SizedBox(height: 14 * _s),
          _ContractCard(
            title: _tr(
              context,
              ko: '소프트웨어 라이선스',
              en: 'Software license',
            ),
            party: 'NotionLite Inc.',
            date: _tr(context, ko: '3일 전', en: '3 days ago'),
            risk: _Risk.low,
            riskLabel: _tr(context, ko: '문제 없음', en: 'Clean'),
          ),
          SizedBox(height: 14 * _s),
          _ContractCard(
            title: _tr(
              context,
              ko: '근로계약서 (수정본)',
              en: 'Employment (revised)',
            ),
            party: _tr(context, ko: '주식회사 메타랩', en: 'MetaLab Inc.'),
            date: _tr(context, ko: '5일 전', en: '5 days ago'),
            risk: _Risk.mid,
            riskLabel: _tr(context, ko: '주의 3건', en: '3 to review'),
          ),
          SizedBox(height: 14 * _s),
          _ContractCard(
            title: _tr(
              context,
              ko: '비밀유지계약서 (NDA)',
              en: 'Non-disclosure (NDA)',
            ),
            party: _tr(
              context,
              ko: '디지털스튜디오 R',
              en: 'Digital Studio R',
            ),
            date: _tr(context, ko: '6일 전', en: '6 days ago'),
            risk: _Risk.low,
            riskLabel: _tr(context, ko: '문제 없음', en: 'Clean'),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(22 * _s),
      decoration: BoxDecoration(
        color: _ink,
        borderRadius: BorderRadius.circular(26 * _s),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _tr(context, ko: '이번 주 위험 신호', en: 'This week\'s risk signal'),
            style: TextStyle(
              fontSize: 14 * _s,
              color: Colors.white.withValues(alpha: .75),
              letterSpacing: 0.4,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 10 * _s),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '9',
                style: TextStyle(
                  fontSize: 56 * _s,
                  height: 1.0,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                ),
              ),
              SizedBox(width: 8 * _s),
              Padding(
                padding: EdgeInsets.only(bottom: 8 * _s),
                child: Text(
                  _tr(context, ko: '건의 위험 조항', en: 'risky clauses'),
                  style: TextStyle(
                    fontSize: 18 * _s,
                    color: Colors.white.withValues(alpha: .85),
                  ),
                ),
              ),
              const Spacer(),
              Container(
                padding: EdgeInsets.symmetric(
                  horizontal: 14 * _s, vertical: 7 * _s,
                ),
                decoration: BoxDecoration(
                  color: _riskHigh,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  _tr(
                    context,
                    ko: '↑ 지난 주 대비 +3',
                    en: '↑ +3 vs. last week',
                  ),
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 13 * _s,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: 20 * _s),
          Row(
            children: [
              _MiniStat(
                label: _tr(context, ko: '높음', en: 'High'),
                value: '4',
                dot: _riskHigh,
              ),
              const SizedBox(width: 44),
              _MiniStat(
                label: _tr(context, ko: '주의', en: 'Watch'),
                value: '5',
                dot: _riskMid,
              ),
              const SizedBox(width: 44),
              _MiniStat(
                label: _tr(context, ko: '안전', en: 'Safe'),
                value: '12',
                dot: _riskLow,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value, required this.dot});
  final String label;
  final String value;
  final Color dot;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 10 * _s, height: 10 * _s,
          decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
        ),
        SizedBox(width: 8 * _s),
        Text(
          '$label  $value',
          style: TextStyle(
            color: Colors.white,
            fontSize: 15 * _s,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 14 * _s,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.0,
        color: _muted,
      ),
    );
  }
}

enum _Risk { high, mid, low }

class _ContractCard extends StatelessWidget {
  const _ContractCard({
    required this.title,
    required this.party,
    required this.date,
    required this.risk,
    required this.riskLabel,
  });
  final String title;
  final String party;
  final String date;
  final _Risk risk;
  final String riskLabel;

  Color get _riskColor => switch (risk) {
        _Risk.high => _riskHigh,
        _Risk.mid => _riskMid,
        _Risk.low => _riskLow,
      };

  IconData get _icon => switch (risk) {
        _Risk.high => Icons.warning_amber_rounded,
        _Risk.mid => Icons.error_outline,
        _Risk.low => Icons.verified_outlined,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(18 * _s),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(22 * _s),
        border: Border.all(color: Colors.black.withValues(alpha: .05)),
      ),
      child: Row(
        children: [
          Container(
            width: 52 * _s, height: 52 * _s,
            decoration: BoxDecoration(
              color: _riskColor.withValues(alpha: .12),
              borderRadius: BorderRadius.circular(14 * _s),
            ),
            child: Icon(_icon, color: _riskColor, size: 26 * _s),
          ),
          SizedBox(width: 16 * _s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 18 * _s,
                    fontWeight: FontWeight.w700,
                    color: _ink,
                  ),
                ),
                SizedBox(height: 3 * _s),
                Text(
                  party,
                  style: TextStyle(fontSize: 14 * _s, color: _muted),
                ),
              ],
            ),
          ),
          SizedBox(width: 8 * _s),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Container(
                padding: EdgeInsets.symmetric(
                  horizontal: 12 * _s, vertical: 5 * _s,
                ),
                decoration: BoxDecoration(
                  color: _riskColor.withValues(alpha: .14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  riskLabel,
                  style: TextStyle(
                    color: _riskColor,
                    fontSize: 13 * _s,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              SizedBox(height: 8 * _s),
              Text(
                date,
                style: TextStyle(fontSize: 13 * _s, color: _muted),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Detail — single contract analysis
// ─────────────────────────────────────────────────────────
class ContractDetailPage extends StatelessWidget {
  const ContractDetailPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      body: ListView(
        padding: EdgeInsets.fromLTRB(
          24 * _s, _statusBarReserve + 14 * _s, 24 * _s, 60 * _s,
        ),
        children: [
          // Custom in-page header (no AppBar) so layout stays under our control.
          Row(
            children: [
              Icon(Icons.arrow_back_ios_new, color: _ink, size: 22 * _s),
              const Spacer(),
              Icon(Icons.ios_share, color: _ink, size: 22 * _s),
              SizedBox(width: 18 * _s),
              Icon(Icons.bookmark_border, color: _ink, size: 22 * _s),
            ],
          ),
          SizedBox(height: 18 * _s),
          Text(
            _tr(context, ko: '주거용 임대차계약서', en: 'Residential lease'),
            style: TextStyle(
              fontSize: 30 * _s,
              fontWeight: FontWeight.w800,
              color: _ink,
              letterSpacing: -0.5,
              height: 1.1,
            ),
          ),
          SizedBox(height: 8 * _s),
          Text(
            _tr(
              context,
              ko: '강남구 역삼동 · 보증금 5,000만원 · 월세 110만원',
              en: 'Yeoksam · ₩50M deposit · ₩1.1M / mo',
            ),
            style: TextStyle(fontSize: 15 * _s, color: _muted),
          ),
          SizedBox(height: 22 * _s),
          const _RiskBanner(),
          SizedBox(height: 28 * _s),
          _SectionLabel(
            _tr(context, ko: '발견된 위험 조항', en: 'Risky clauses found'),
          ),
          SizedBox(height: 14 * _s),
          _ClauseCard(
            n: '01',
            title: _tr(
              context,
              ko: '일방적 계약 해지 조항',
              en: 'Unilateral termination clause',
            ),
            snippet: _tr(
              context,
              ko: '"임대인은 사전 통보 없이 30일 내 계약을 해지할 수 있다."',
              en: '"Landlord may terminate within 30 days without prior notice."',
            ),
            risk: _Risk.high,
            riskLabel: _tr(context, ko: '높음', en: 'High'),
            reason: _tr(
              context,
              ko: '주택임대차보호법 제6조에 반함',
              en: 'Conflicts with Housing Lease Protection Act §6',
            ),
          ),
          SizedBox(height: 14 * _s),
          _ClauseCard(
            n: '02',
            title: _tr(
              context,
              ko: '과도한 원상복구 의무',
              en: 'Excessive restoration duty',
            ),
            snippet: _tr(
              context,
              ko: '"임차인은 모든 벽지·바닥재를 신품으로 교체한다."',
              en: '"Tenant replaces all wallpaper and flooring with new."',
            ),
            risk: _Risk.high,
            riskLabel: _tr(context, ko: '높음', en: 'High'),
            reason: _tr(
              context,
              ko: '통상의 사용에 따른 마모는 제외해야 함',
              en: 'Ordinary wear and tear must be excluded',
            ),
          ),
          SizedBox(height: 14 * _s),
          _ClauseCard(
            n: '03',
            title: _tr(
              context,
              ko: '관할 법원 편향',
              en: 'Biased venue clause',
            ),
            snippet: _tr(
              context,
              ko: '"분쟁 발생 시 임대인 주소지 법원을 관할로 한다."',
              en: '"Disputes resolved at the court of the landlord\'s address."',
            ),
            risk: _Risk.mid,
            riskLabel: _tr(context, ko: '주의', en: 'Watch'),
            reason: _tr(
              context,
              ko: '소비자 거주지 관할 원칙과 상이',
              en: 'Differs from consumer-residence venue rule',
            ),
          ),
          SizedBox(height: 28 * _s),
          Container(
            padding: EdgeInsets.symmetric(vertical: 18 * _s),
            decoration: BoxDecoration(
              color: _ink,
              borderRadius: BorderRadius.circular(18 * _s),
            ),
            child: Center(
              child: Text(
                _tr(context, ko: '전체 보고서 보기', en: 'View full report'),
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 17 * _s,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskBanner extends StatelessWidget {
  const _RiskBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(20 * _s),
      decoration: BoxDecoration(
        color: _riskHigh.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(22 * _s),
        border: Border.all(color: _riskHigh.withValues(alpha: .25)),
      ),
      child: Row(
        children: [
          Container(
            width: 52 * _s, height: 52 * _s,
            decoration: const BoxDecoration(
              color: _riskHigh,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.warning_amber_rounded,
              color: Colors.white,
              size: 28 * _s,
            ),
          ),
          SizedBox(width: 16 * _s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _tr(context, ko: '위험도 높음', en: 'High risk'),
                  style: TextStyle(
                    fontSize: 18 * _s,
                    fontWeight: FontWeight.w800,
                    color: _riskHigh,
                  ),
                ),
                SizedBox(height: 3 * _s),
                Text(
                  _tr(
                    context,
                    ko: '계약 전 4개 조항을 협의하세요',
                    en: 'Renegotiate 4 clauses before signing',
                  ),
                  style: TextStyle(fontSize: 14 * _s, color: _ink),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ClauseCard extends StatelessWidget {
  const _ClauseCard({
    required this.n,
    required this.title,
    required this.snippet,
    required this.risk,
    required this.riskLabel,
    required this.reason,
  });
  final String n;
  final String title;
  final String snippet;
  final _Risk risk;
  final String riskLabel;
  final String reason;

  Color get _riskColor => switch (risk) {
        _Risk.high => _riskHigh,
        _Risk.mid => _riskMid,
        _Risk.low => _riskLow,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(18 * _s),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(22 * _s),
        border: Border.all(color: Colors.black.withValues(alpha: .05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                n,
                style: TextStyle(
                  fontSize: 13 * _s,
                  fontWeight: FontWeight.w800,
                  color: _muted,
                  letterSpacing: 1,
                ),
              ),
              SizedBox(width: 12 * _s),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 18 * _s,
                    fontWeight: FontWeight.w700,
                    color: _ink,
                  ),
                ),
              ),
              Container(
                padding: EdgeInsets.symmetric(
                  horizontal: 12 * _s, vertical: 5 * _s,
                ),
                decoration: BoxDecoration(
                  color: _riskColor.withValues(alpha: .14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  riskLabel,
                  style: TextStyle(
                    color: _riskColor,
                    fontSize: 13 * _s,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: 12 * _s),
          Container(
            padding: EdgeInsets.all(14 * _s),
            decoration: BoxDecoration(
              color: _bgColor,
              borderRadius: BorderRadius.circular(14 * _s),
            ),
            child: Text(
              snippet,
              style: TextStyle(
                fontSize: 15 * _s,
                color: _ink,
                height: 1.45,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
          SizedBox(height: 10 * _s),
          Row(
            children: [
              Icon(Icons.info_outline, size: 16 * _s, color: _muted),
              SizedBox(width: 7 * _s),
              Expanded(
                child: Text(
                  reason,
                  style: TextStyle(fontSize: 13 * _s, color: _muted),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Search — focused TextField raises the system keyboard
// ─────────────────────────────────────────────────────────
class ContractSearchPage extends StatefulWidget {
  const ContractSearchPage({super.key});

  @override
  State<ContractSearchPage> createState() => _ContractSearchPageState();
}

class _ContractSearchPageState extends State<ContractSearchPage> {
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    // Request focus after first frame so the keyboard rises as soon as
    // the screen settles. shotgun's `keyboard_show` action waits for
    // the entrance animation; this side prepares the focus.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focus.requestFocus();
    });
  }

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      body: ListView(
        padding: EdgeInsets.fromLTRB(
          24 * _s, _statusBarReserve + 14 * _s, 24 * _s, 60 * _s,
        ),
        children: [
          Row(
            children: [
              Icon(Icons.arrow_back_ios_new, color: _ink, size: 22 * _s),
              SizedBox(width: 12 * _s),
              Expanded(
                child: Container(
                  height: 44 * _s,
                  padding: EdgeInsets.symmetric(horizontal: 14 * _s),
                  decoration: BoxDecoration(
                    color: _cardColor,
                    borderRadius: BorderRadius.circular(14 * _s),
                    border: Border.all(
                      color: Colors.black.withValues(alpha: .06),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.search, color: _muted, size: 20 * _s),
                      SizedBox(width: 10 * _s),
                      Expanded(
                        child: TextField(
                          focusNode: _focus,
                          autofocus: true,
                          style: TextStyle(fontSize: 16 * _s, color: _ink),
                          decoration: InputDecoration(
                            border: InputBorder.none,
                            isCollapsed: true,
                            hintText: _tr(
                              context,
                              ko: '계약서, 조항, 상대방 검색',
                              en: 'Search contracts, clauses, parties',
                            ),
                            hintStyle: TextStyle(
                              fontSize: 16 * _s,
                              color: _muted,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: 20 * _s),
          _SectionLabel(_tr(context, ko: '최근 검색', en: 'Recent searches')),
          SizedBox(height: 10 * _s),
          for (final term in _tr(
            context,
            ko: '임대차계약서|해지 조항|NDA 비밀유지|위약금',
            en: 'Residential lease|Termination|NDA|Liquidated damages',
          ).split('|'))
            Padding(
              padding: EdgeInsets.symmetric(vertical: 6 * _s),
              child: Row(
                children: [
                  Icon(Icons.history, size: 18 * _s, color: _muted),
                  SizedBox(width: 12 * _s),
                  Expanded(
                    child: Text(
                      term,
                      style: TextStyle(fontSize: 16 * _s, color: _ink),
                    ),
                  ),
                  Icon(Icons.north_west, size: 16 * _s, color: _muted),
                ],
              ),
            ),
          SizedBox(height: 20 * _s),
          _SectionLabel(_tr(context, ko: '추천 키워드', en: 'Suggested')),
          SizedBox(height: 10 * _s),
          Wrap(
            spacing: 8 * _s,
            runSpacing: 8 * _s,
            children: [
              for (final kw in _tr(
                context,
                ko: '주거 임대차|프리랜서 계약|근로계약 수정|법원 관할|원상복구',
                en: 'Lease|Freelance|Employment|Venue|Restoration',
              ).split('|'))
                Container(
                  padding: EdgeInsets.symmetric(
                    horizontal: 14 * _s,
                    vertical: 8 * _s,
                  ),
                  decoration: BoxDecoration(
                    color: _cardColor,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(
                      color: Colors.black.withValues(alpha: .06),
                    ),
                  ),
                  child: Text(
                    kw,
                    style: TextStyle(fontSize: 13 * _s, color: _ink),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
