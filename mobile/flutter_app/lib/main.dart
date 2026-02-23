import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/models.dart';
import 'core/session_store.dart';
import 'ui/auth_page.dart';
import 'ui/home_page.dart';

const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

void main() {
  runApp(const NebulaGuardApp());
}

class NebulaGuardApp extends StatelessWidget {
  const NebulaGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFFC8A56A);
    return MaterialApp(
      title: 'NebulaGuard 社区端',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      home: const AppController(),
    );
  }
}

class AppController extends StatefulWidget {
  const AppController({super.key});

  @override
  State<AppController> createState() => _AppControllerState();
}

class _AppControllerState extends State<AppController> {
  final _session = SessionStore();
  late final ApiClient _api;

  bool _booting = true;
  bool _authLoading = false;
  String _authError = '';
  AuthUser? _user;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: apiBaseUrl);
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final token = await _session.readToken();
    if (token.isNotEmpty) {
      _api.setToken(token);
      try {
        final me = await _api.fetchMe();
        if (mounted) {
          setState(() {
            _user = me;
          });
        }
      } catch (_) {
        await _session.clearToken();
        _api.setToken('');
      }
    }
    if (mounted) {
      setState(() => _booting = false);
    }
  }

  Future<void> _login(String username, String password) async {
    setState(() {
      _authLoading = true;
      _authError = '';
    });
    try {
      final payload = await _api.login(username: username, password: password);
      _api.setToken(payload.token);
      await _session.saveToken(payload.token);
      if (mounted) {
        setState(() => _user = payload.user);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _authError = '$e');
      }
    } finally {
      if (mounted) {
        setState(() => _authLoading = false);
      }
    }
  }

  Future<void> _register(
    String username,
    String displayName,
    String password,
    String communityName,
    String communityDistrict,
  ) async {
    setState(() {
      _authLoading = true;
      _authError = '';
    });
    try {
      final payload = await _api.register(
        username: username,
        displayName: displayName,
        password: password,
        communityName: communityName,
        communityDistrict: communityDistrict,
      );
      _api.setToken(payload.token);
      await _session.saveToken(payload.token);
      if (mounted) {
        setState(() => _user = payload.user);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _authError = '$e');
      }
    } finally {
      if (mounted) {
        setState(() => _authLoading = false);
      }
    }
  }

  Future<void> _logout() async {
    await _session.clearToken();
    _api.setToken('');
    if (mounted) {
      setState(() {
        _user = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_booting) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_user == null) {
      return AuthPage(
        loading: _authLoading,
        errorText: _authError,
        onLogin: _login,
        onRegister: _register,
      );
    }

    return MobileHomePage(user: _user!, api: _api, onLogout: _logout);
  }
}
