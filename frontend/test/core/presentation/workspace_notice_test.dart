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
            home: const Scaffold(
              body: WorkspaceHeader(
                title: '搜索本地资料',
                description: '描述你记得的内容，找到对应文件和位置',
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
      try {
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: Scaffold(
              body: WorkspaceNotice(
                tone: WorkspaceNoticeTone.error,
                message: '无法加载索引库。',
                actionLabel: '重新尝试',
                onAction: () => retryCount += 1,
                announce: true,
              ),
            ),
          ),
        );

        final notice = find.byKey(const Key('workspace-notice'));
        expect(notice, findsOneWidget);
        expect(
          tester.getSemantics(notice).flagsCollection.isLiveRegion,
          isTrue,
        );
        final retry = find.bySemanticsLabel('重新尝试');
        expect(retry, findsOneWidget);
        await tester.tap(retry);
        expect(retryCount, 1);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      } finally {
        semantics.dispose();
      }
    },
  );
}
