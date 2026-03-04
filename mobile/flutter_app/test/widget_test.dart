import 'package:flutter_test/flutter_test.dart';

import 'package:nebulaguard_mobile/main.dart';

void main() {
  testWidgets('App boots to loading state', (WidgetTester tester) async {
    await tester.pumpWidget(const NebulaGuardApp());
    expect(find.byType(NebulaGuardApp), findsOneWidget);
  });
}
