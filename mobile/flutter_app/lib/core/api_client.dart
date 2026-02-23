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
    if (detail is List && detail.isNotEmpty && detail.first is Map<String, dynamic>) {
      final msg = (detail.first['msg'] ?? '').toString();
      if (msg.isNotEmpty) {
        throw ApiException(msg);
      }
    }
    throw ApiException('请求失败：HTTP ${resp.statusCode}');
  }

  Future<AuthPayload> login({required String username, required String password}) async {
    final resp = await http.post(
      _uri('/auth/login'),
      headers: _headers(),
      body: jsonEncode({'username': username, 'password': password}),
    );
    final data = await _decode(resp);
    return AuthPayload.fromJson(data);
  }

  Future<AuthPayload> register({
    required String username,
    required String displayName,
    required String password,
    required String communityName,
    String communityDistrict = '成都市',
  }) async {
    final resp = await http.post(
      _uri('/auth/register'),
      headers: _headers(),
      body: jsonEncode({
        'username': username,
        'display_name': displayName,
        'password': password,
        'community_name': communityName,
        'community_district': communityDistrict,
      }),
    );
    final data = await _decode(resp);
    return AuthPayload.fromJson(data);
  }

  Future<AuthUser> fetchMe() async {
    final resp = await http.get(_uri('/auth/me'), headers: _headers(jsonBody: false));
    final data = await _decode(resp);
    return AuthUser.fromJson((data['user'] ?? <String, dynamic>{}) as Map<String, dynamic>);
  }

  Future<List<ChatMessage>> fetchChatMessages({int limit = 100}) async {
    final resp = await http.get(
      _uri('/community/chat/messages', {'limit': limit}),
      headers: _headers(jsonBody: false),
    );
    final data = await _decode(resp);
    final items = data['items'];
    if (items is! List) return [];
    return items
        .whereType<Map>()
        .map((item) => ChatMessage.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  Future<void> sendChatMessage({required String content, bool askAi = false}) async {
    final resp = await http.post(
      _uri('/community/chat/send'),
      headers: _headers(),
      body: jsonEncode({'content': content, 'ask_ai': askAi}),
    );
    await _decode(resp);
  }

  Future<AssistantAskResult> askAssistant(String question) async {
    final resp = await http.post(
      _uri('/community/assistant/ask'),
      headers: _headers(),
      body: jsonEncode({'question': question}),
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
    final resp = await http.post(
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
    );
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
    final resp = await http.post(
      _uri('/residents/checkins'),
      headers: _headers(),
      body: jsonEncode({
        'subject_name': subjectName,
        'relation': relation,
        'status': status,
        'notes': notes,
        if (lat != null) 'lat': lat,
        if (lng != null) 'lng': lng,
        if (incidentId != null && incidentId.isNotEmpty) 'incident_id': incidentId,
      }),
    );
    await _decode(resp);
  }

  Future<CheckinSummary> fetchCheckinSummary() async {
    final resp = await http.get(
      _uri('/residents/checkins/summary'),
      headers: _headers(jsonBody: false),
    );
    final data = await _decode(resp);
    return CheckinSummary.fromJson(data);
  }

  Future<List<IncidentItem>> fetchIncidents({int limit = 80}) async {
    final resp = await http.get(
      _uri('/incidents', {'limit': limit}),
      headers: _headers(jsonBody: false),
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
    final resp = await http.get(
      _uri('/shelters', {'limit': limit}),
      headers: _headers(jsonBody: false),
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
