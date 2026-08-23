import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'workspace header keeps its heading separate at large text without overflow',
    (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.binding.setSurfaceSize(const Size(560, 420));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      try {
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: Scaffold(
              body: WorkspaceHeader(
                title: '搜索本地资料',
                description: '描述你记得的内容，找到对应文件和位置',
                actions: [
                  TextButton(
                    key: const Key('header-filter-action'),
                    onPressed: () {},
                    child: const Text('筛选'),
                  ),
                  TextButton(
                    key: const Key('header-refresh-action'),
                    onPressed: () {},
                    child: const Text('刷新'),
                  ),
                ],
              ),
            ),
          ),
        );

        final header = find.byKey(const Key('workspace-header'));
        expect(header, findsOneWidget);
        final heading = find.descendant(
          of: header,
          matching: find.byWidgetPredicate(
            (widget) => widget is Semantics && widget.properties.header == true,
          ),
        );
        expect(heading, findsOneWidget);
        final headingData = tester.getSemantics(heading).getSemanticsData();
        expect(headingData.label, '搜索本地资料');
        expect(headingData.flagsCollection.isHeader, isTrue);
        final description = find.semantics.byLabel('描述你记得的内容，找到对应文件和位置');
        final descriptionText = find.text('描述你记得的内容，找到对应文件和位置');
        expect(description, findsOneWidget);
        expect(
          description
              .evaluate()
              .single
              .getSemanticsData()
              .flagsCollection
              .isHeader,
          isFalse,
        );
        final filterAction = find.byKey(const Key('header-filter-action'));
        final refreshAction = find.byKey(const Key('header-refresh-action'));
        expect(filterAction, findsOneWidget);
        expect(refreshAction, findsOneWidget);
        final descriptionBottom = tester.getBottomLeft(descriptionText).dy;
        expect(
          tester.getTopLeft(filterAction).dy,
          greaterThan(descriptionBottom),
        );
        expect(
          tester.getTopLeft(refreshAction).dy,
          greaterThan(descriptionBottom),
        );
        expect(tester.takeException(), isNull);
      } finally {
        semantics.dispose();
      }
    },
  );

  testWidgets(
    'error notice announces and invokes its named action with an accessible target',
    (tester) async {
      final semantics = tester.ensureSemantics();
      var retryCount = 0;
      var dismissCount = 0;
      await tester.binding.setSurfaceSize(const Size(320, 420));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      try {
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: Scaffold(
              body: WorkspaceNotice(
                tone: WorkspaceNoticeTone.error,
                message: '无法加载索引库。',
                actionLabel: '重新尝试',
                onAction: () => retryCount += 1,
                onDismiss: () => dismissCount += 1,
                announce: true,
              ),
            ),
          ),
        );

        final notice = find.byKey(const Key('workspace-notice'));
        expect(notice, findsOneWidget);
        expect(find.text('无法加载索引库。'), findsOneWidget);
        expect(
          tester.getSemantics(notice).flagsCollection.isLiveRegion,
          isTrue,
        );
        final retry = find.bySemanticsLabel('重新尝试');
        final dismiss = find.byTooltip('关闭提示');
        expect(retry, findsOneWidget);
        expect(dismiss, findsOneWidget);
        final message = find.text('无法加载索引库。');
        final messageBottom = tester.getBottomLeft(message).dy;
        expect(tester.getTopLeft(retry).dy, greaterThan(messageBottom));
        expect(tester.getTopLeft(dismiss).dy, greaterThan(messageBottom));
        expect(
          tester.getSemantics(retry).rect.height,
          greaterThanOrEqualTo(48),
        );
        expect(
          tester.getSemantics(dismiss).rect.height,
          greaterThanOrEqualTo(48),
        );
        await tester.tap(retry);
        await tester.tap(dismiss);
        expect(retryCount, 1);
        expect(dismissCount, 1);
        expect(tester.takeException(), isNull);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      } finally {
        semantics.dispose();
      }
    },
  );
}
