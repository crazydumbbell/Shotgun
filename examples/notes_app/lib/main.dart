import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  runApp(const MyApp());
}

// ─────────────────────────────────────────────────────────
// Tiny localization table — just enough to demo shotgun's
// per-locale capture. Real apps would use flutter_localizations.
// ─────────────────────────────────────────────────────────
class L {
  static String _lang(BuildContext c) => Localizations.localeOf(c).languageCode;
  static const _t = <String, Map<String, String>>{
    'app_title': {'en': 'Notes', 'ko': '노트'},
    'today': {'en': 'Today', 'ko': '오늘'},
    'pinned': {'en': 'Pinned', 'ko': '고정됨'},
    'search_hint': {'en': 'Search notes', 'ko': '노트 검색'},
    'new_note': {'en': 'New note', 'ko': '새 노트'},
    'search_results': {'en': 'Results for "coffee"', 'ko': '"커피" 검색 결과'},
    'note_1_title': {'en': 'Morning ritual', 'ko': '아침 루틴'},
    'note_1_body': {
      'en': 'Pour-over, no sugar. Light roast — single-origin Ethiopian.\n\n'
          'Heat water to 94°C. Use 18g of coffee to 300g water (1:16.7 ratio). '
          'Bloom for 30 seconds with 50g of water, then pour in steady spirals '
          'every minute.\n\n'
          'Total brew time 3:00. Tastes brightest in the first 10 minutes.',
      'ko': '핸드드립, 무가당. 라이트 로스트 — 에티오피아 싱글 오리진.\n\n'
          '물 온도 94°C, 원두 18g 대 물 300g (1:16.7 비율). 50g으로 30초 '
          '블루밍 후, 1분 간격으로 안정적인 나선을 그리며 부어줍니다.\n\n'
          '총 추출 3분. 처음 10분이 가장 밝은 향이 살아있는 시점입니다.',
    },
    'note_2_title': {'en': 'Weekend trip', 'ko': '주말 여행'},
    'note_3_title': {'en': 'Reading list', 'ko': '읽을 책'},
    'note_4_title': {'en': 'Bouldering goals', 'ko': '볼더링 목표'},
    'note_5_title': {'en': 'Coffee beans to try', 'ko': '시도해볼 원두'},
    'updated_just_now': {'en': 'Just now', 'ko': '방금 전'},
    'updated_yesterday': {'en': 'Yesterday', 'ko': '어제'},
    'updated_2d_ago': {'en': '2 days ago', 'ko': '2일 전'},
  };
  static String of(BuildContext c, String key) =>
      _t[key]?[_lang(c)] ?? _t[key]?['en'] ?? key;
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF7C5CF0),
      brightness: Brightness.light,
    );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: scheme,
        useMaterial3: true,
        scaffoldBackgroundColor: scheme.surface,
      ),
      supportedLocales: const [Locale('en'), Locale('ko')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      initialRoute: '/',
      routes: {
        '/': (_) => const HomePage(),
        '/note/1': (_) => const NoteDetailPage(noteIndex: 1),
        '/search': (_) => const SearchPage(),
      },
    );
  }
}

// ─────────────────────────────────────────────────────────
// Home — list of notes
// ─────────────────────────────────────────────────────────
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 28, 20, 100),
          children: [
            Text(
              L.of(context, 'app_title'),
              style: theme.textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            _SearchBar(),
            const SizedBox(height: 28),
            _SectionLabel(L.of(context, 'pinned')),
            _NoteCard(
              title: L.of(context, 'note_1_title'),
              preview: L.of(context, 'note_1_body'),
              updated: L.of(context, 'updated_just_now'),
              pinned: true,
              color: const Color(0xFFFFE9B0),
            ),
            const SizedBox(height: 16),
            _SectionLabel(L.of(context, 'today')),
            _NoteCard(
              title: L.of(context, 'note_2_title'),
              preview: 'Reservation Fri 19:30 · Anseong → Yeongwol',
              updated: L.of(context, 'updated_just_now'),
              color: const Color(0xFFD6E8FF),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: L.of(context, 'note_3_title'),
              preview: '1. The Pragmatic Programmer\n2. Designing Data-Intensive…',
              updated: L.of(context, 'updated_yesterday'),
              color: const Color(0xFFE6FFE2),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: L.of(context, 'note_4_title'),
              preview: 'V4 outdoor by end of season',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFFFDFE6),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: L.of(context, 'note_5_title'),
              preview: 'Yirgacheffe · Bourbon · Geisha · Mocha-Java',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFFFE9B0),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: 'Groceries',
              preview: 'Milk · Eggs · Sourdough · Spinach · Tomatoes · Olive oil',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFD6E8FF),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: 'Apartment ideas',
              preview: 'Move desk near window. Plants on the shelf. New rug.',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFE6FFE2),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {},
        icon: const Icon(Icons.edit_outlined),
        label: Text(L.of(context, 'new_note')),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Note detail — single note open
// ─────────────────────────────────────────────────────────
class NoteDetailPage extends StatelessWidget {
  const NoteDetailPage({super.key, required this.noteIndex});
  final int noteIndex;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFFFFF8E5),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFFF8E5),
        elevation: 0,
        leading: const BackButton(),
        actions: const [
          Icon(Icons.push_pin, size: 22),
          SizedBox(width: 16),
          Icon(Icons.more_horiz, size: 22),
          SizedBox(width: 16),
        ],
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
          children: [
            Text(
              L.of(context, 'updated_just_now'),
              style: theme.textTheme.labelMedium?.copyWith(
                color: Colors.black.withValues(alpha: .55),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              L.of(context, 'note_1_title'),
              style: theme.textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              L.of(context, 'note_1_body'),
              style: theme.textTheme.bodyLarge?.copyWith(
                height: 1.55, fontSize: 18,
              ),
            ),
            const SizedBox(height: 32),
            const _Checklist(),
          ],
        ),
      ),
    );
  }
}

class _Checklist extends StatelessWidget {
  const _Checklist();
  @override
  Widget build(BuildContext context) {
    final items = [
      ('Grind 18g medium-fine', true),
      ('Pre-wet filter', true),
      ('Bloom 30s with 50g water', true),
      ('First pour to 150g', false),
      ('Second pour to 220g', false),
      ('Final pour to 300g', false),
      ('Stir, swirl, settle', false),
      ('Decant & serve', false),
    ];
    return Column(
      children: [
        for (final (text, done) in items)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                Icon(
                  done ? Icons.check_box : Icons.check_box_outline_blank,
                  color: done ? Colors.deepPurple : Colors.black54,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    text,
                    style: TextStyle(
                      fontSize: 17,
                      decoration: done ? TextDecoration.lineThrough : null,
                      color: done ? Colors.black54 : Colors.black87,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────
// Search — filtered list
// ─────────────────────────────────────────────────────────
class SearchPage extends StatelessWidget {
  const SearchPage({super.key});
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
          children: [
            const Align(
              alignment: Alignment.centerLeft,
              child: BackButton(),
            ),
            const SizedBox(height: 4),
            _SearchBar(initial: 'coffee'),
            const SizedBox(height: 24),
            Text(
              L.of(context, 'search_results'),
              style: theme.textTheme.titleMedium?.copyWith(
                color: Colors.black.withValues(alpha: .6),
              ),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: L.of(context, 'note_1_title'),
              preview: L.of(context, 'note_1_body'),
              updated: L.of(context, 'updated_just_now'),
              color: const Color(0xFFFFE9B0),
              highlight: 'coffee',
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: L.of(context, 'note_5_title'),
              preview: 'Yirgacheffe · Bourbon · Geisha · Mocha-Java',
              updated: L.of(context, 'updated_yesterday'),
              color: const Color(0xFFE6FFE2),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: 'Coffee shops near home',
              preview: 'Anthracite · Coffee Libre · Fritz · Center Coffee · '
                  'Felt · Hell Cafe · Manufact',
              updated: L.of(context, 'updated_yesterday'),
              color: const Color(0xFFD6E8FF),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: 'Coffee gear wishlist',
              preview: 'Comandante C40 · Hario V60 · Acaia Pearl · Fellow Stagg',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFFFDFE6),
            ),
            const SizedBox(height: 12),
            _NoteCard(
              title: 'Café experiments',
              preview: 'Cold brew 1:8, 18hr · Iced V60 with calendar ice',
              updated: L.of(context, 'updated_2d_ago'),
              color: const Color(0xFFFFE9B0),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Shared widgets
// ─────────────────────────────────────────────────────────
class _SearchBar extends StatelessWidget {
  const _SearchBar({this.initial});
  final String? initial;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: .05),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(Icons.search, color: Colors.black.withValues(alpha: .55)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              initial ?? L.of(context, 'search_hint'),
              style: TextStyle(
                fontSize: 17,
                color: initial != null
                    ? Colors.black87
                    : Colors.black.withValues(alpha: .5),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, top: 4),
      child: Text(
        text.toUpperCase(),
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
          color: Colors.black.withValues(alpha: .55),
        ),
      ),
    );
  }
}

class _NoteCard extends StatelessWidget {
  const _NoteCard({
    required this.title,
    required this.preview,
    required this.updated,
    required this.color,
    this.pinned = false,
    this.highlight,
  });
  final String title;
  final String preview;
  final String updated;
  final Color color;
  final bool pinned;
  final String? highlight;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (pinned) const Icon(Icons.push_pin, size: 18),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            preview,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 15, height: 1.4,
              color: Colors.black.withValues(alpha: .72),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            updated,
            style: TextStyle(
              fontSize: 13,
              color: Colors.black.withValues(alpha: .55),
            ),
          ),
        ],
      ),
    );
  }
}
