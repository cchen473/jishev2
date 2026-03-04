import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  String _token = '';
  static const Duration _defaultRequestTimeout = Duration(seconds: 10);
  static const Duration _probeTimeout = Duration(seconds: 2);

  ApiClient({required this.baseUrl, String token = ''}) : _token = token;

  void setToken(String token) {
    _token = token;
  }

  Map<String, String> _headers({bool jsonBody = true}) {
    final headers = <String, String>{};
    if (jsonBody) {
      headers['Content-Type'] = 'application/json';
    }
    if (_token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_token';
    }
    return headers;
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final normalized = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$baseUrl$normalized').replace(
      queryParameters: query?.map((key, value) => MapEntry(key, '$value')),
    );
  }

  Uri websocketUri({required String token}) {
    final base = Uri.parse(baseUrl);
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    return Uri(
      scheme: scheme,
      host: base.host,
      port: base.hasPort ? base.port : null,
      path: '/ws/mission',
      queryParameters: {'token': token},
    );
  }

  Future<http.Response> _withTimeout(
    Future<http.Response> request, {
    required String action,
    Duration? timeout,
  }) async {
    try {
      return await request.timeout(timeout ?? _defaultRequestTimeout);
    } on TimeoutException {
      throw ApiException('$action 超时，请检查网络或服务状态');
    }
  }

  Future<Map<String, dynamic>> _decode(http.Response resp) async {
    final raw = resp.body;
    final parsed = raw.isEmpty ? <String, dynamic>{} : jsonDecode(raw);
    if (parsed is! Map<String, dynamic>) {
      throw ApiException('服务返回格式异常');
    }
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return parsed;
    }

    final detail = parsed['detail'];
    if (detail is String && detail.trim().isNotEmpty) {
      throw ApiException(detail);
    }
    if (detail is List &&
        detail.isNotEmpty &&
        detail.first is Map<String, dynamic>) {
      final msg = (detail.first['msg'] ?? '').toString();
      if (msg.isNotEmpty) {
        throw ApiException(msg);
      }
    }
    throw ApiException('请求失败：HTTP ${resp.statusCode}');
  }

  Future<AuthPayload> login(
      {required String username, required String password}) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/auth/login'),
        headers: _headers(),
        body: jsonEncode({'username': username, 'password': password}),
      ),
      action: '登录请求',
    );
    final data = await _decode(resp);
    return AuthPayload.fromJson(data);
  }

  Future<void> pingBackend() async {
    final resp = await _withTimeout(
      http.get(
        _uri('/'),
        headers: _headers(jsonBody: false),
      ),
      action: '后端连通性检测',
      timeout: _probeTimeout,
    );
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw ApiException('后端连通性检测失败：HTTP ${resp.statusCode}');
    }
  }

  Future<void> pingHealth() => pingBackend();

  Future<AuthPayload> register({
    required String username,
    required String displayName,
    required String password,
    required String communityName,
    String communityDistrict = '成都市',
  }) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/auth/register'),
        headers: _headers(),
        body: jsonEncode({
          'username': username,
          'display_name': displayName,
          'password': password,
          'community_name': communityName,
          'community_district': communityDistrict,
        }),
      ),
      action: '注册请求',
    );
    final data = await _decode(resp);
    return AuthPayload.fromJson(data);
  }

  Future<AuthUser> fetchMe() async {
    final resp = await _withTimeout(
      http.get(_uri('/auth/me'), headers: _headers(jsonBody: false)),
      action: '用户信息请求',
    );
    final data = await _decode(resp);
    return AuthUser.fromJson(
        (data['user'] ?? <String, dynamic>{}) as Map<String, dynamic>);
  }

  Future<List<ChatMessage>> fetchChatMessages({int limit = 100}) async {
    final resp = await _withTimeout(
      http.get(
        _uri('/community/chat/messages', {'limit': limit}),
        headers: _headers(jsonBody: false),
      ),
      action: '群聊拉取请求',
    );
    final data = await _decode(resp);
    final items = data['items'];
    if (items is! List) return [];
    return items
        .whereType<Map>()
        .map((item) => ChatMessage.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  Future<void> sendChatMessage(
      {required String content, bool askAi = false}) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/community/chat/send'),
        headers: _headers(),
        body: jsonEncode({'content': content, 'ask_ai': askAi}),
      ),
      action: '群聊发送请求',
    );
    await _decode(resp);
  }

  Future<AssistantAskResult> askAssistant(String question) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/community/assistant/ask'),
        headers: _headers(),
        body: jsonEncode({'question': question}),
      ),
      action: 'AI 助手请求',
      timeout: const Duration(seconds: 45),
    );
    final data = await _decode(resp);
    return AssistantAskResult.fromJson(data);
  }

  Future<List<String>> submitEarthquakeReport({
    required double lat,
    required double lng,
    required int feltLevel,
    required String buildingType,
    required String structureNotes,
    required String description,
  }) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/report/earthquake'),
        headers: _headers(),
        body: jsonEncode({
          'lat': lat,
          'lng': lng,
          'felt_level': feltLevel,
          'building_type': buildingType,
          'structure_notes': structureNotes,
          'description': description,
        }),
      ),
      action: '地震上报请求',
    );
    final data = await _decode(resp);
    final advice = data['shelter_advice'];
    if (advice is List) {
      return advice.map((e) => '$e').toList();
    }
    return [];
  }

  Future<List<String>> submitEarthquakeReportWithImage({
    required double lat,
    required double lng,
    required int feltLevel,
    required String buildingType,
    required String structureNotes,
    required String description,
    required String imagePath,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/report/earthquake_with_media'),
    );
    request.headers.addAll(_headers(jsonBody: false));
    request.fields['lat'] = '$lat';
    request.fields['lng'] = '$lng';
    request.fields['felt_level'] = '$feltLevel';
    request.fields['building_type'] = buildingType;
    request.fields['structure_notes'] = structureNotes;
    request.fields['description'] = description;
    request.files.add(await http.MultipartFile.fromPath('image', imagePath));
    http.StreamedResponse streamed;
    try {
      streamed = await request.send().timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw ApiException('地震上报请求超时，请检查网络或服务状态');
    }
    final resp = await http.Response.fromStream(streamed);
    final data = await _decode(resp);
    final advice = data['shelter_advice'];
    if (advice is List) {
      return advice.map((e) => '$e').toList();
    }
    return [];
  }

  Future<void> submitResidentCheckin({
    required String subjectName,
    required String relation,
    required String status,
    String notes = '',
    double? lat,
    double? lng,
    String? incidentId,
  }) async {
    final resp = await _withTimeout(
      http.post(
        _uri('/residents/checkins'),
        headers: _headers(),
        body: jsonEncode({
          'subject_name': subjectName,
          'relation': relation,
          'status': status,
          'notes': notes,
          if (lat != null) 'lat': lat,
          if (lng != null) 'lng': lng,
          if (incidentId != null && incidentId.isNotEmpty)
            'incident_id': incidentId,
        }),
      ),
      action: '报平安提交请求',
    );
    await _decode(resp);
  }

  Future<CheckinSummary> fetchCheckinSummary() async {
    final resp = await _withTimeout(
      http.get(
        _uri('/residents/checkins/summary'),
        headers: _headers(jsonBody: false),
      ),
      action: '报平安统计请求',
    );
    final data = await _decode(resp);
    return CheckinSummary.fromJson(data);
  }

  Future<List<IncidentItem>> fetchIncidents({int limit = 80}) async {
    final resp = await _withTimeout(
      http.get(
        _uri('/incidents', {'limit': limit}),
        headers: _headers(jsonBody: false),
      ),
      action: '事件列表请求',
    );
    final data = await _decode(resp);
    final items = data['items'];
    if (items is! List) return [];
    return items
        .whereType<Map>()
        .map((item) => IncidentItem.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  Future<List<ShelterItem>> fetchShelters({int limit = 80}) async {
    final resp = await _withTimeout(
      http.get(
        _uri('/shelters', {'limit': limit}),
        headers: _headers(jsonBody: false),
      ),
      action: '避难点列表请求',
    );
    final data = await _decode(resp);
    final items = data['items'];
    if (items is! List) return [];
    return items
        .whereType<Map>()
        .map((item) => ShelterItem.fromJson(item.cast<String, dynamic>()))
        .toList();
  }
}
