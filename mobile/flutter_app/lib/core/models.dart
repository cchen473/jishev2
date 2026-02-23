class CommunityInfo {
  final String id;
  final String name;
  final String district;
  final double baseLat;
  final double baseLng;
  final String role;

  CommunityInfo({
    required this.id,
    required this.name,
    required this.district,
    required this.baseLat,
    required this.baseLng,
    required this.role,
  });

  factory CommunityInfo.fromJson(Map<String, dynamic> json) {
    return CommunityInfo(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      district: (json['district'] ?? '').toString(),
      baseLat: _asDouble(json['base_lat']),
      baseLng: _asDouble(json['base_lng']),
      role: (json['role'] ?? 'member').toString(),
    );
  }
}

class AuthUser {
  final String id;
  final String username;
  final String displayName;
  final CommunityInfo? community;

  AuthUser({
    required this.id,
    required this.username,
    required this.displayName,
    required this.community,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: (json['id'] ?? '').toString(),
      username: (json['username'] ?? '').toString(),
      displayName: (json['display_name'] ?? '').toString(),
      community: json['community'] is Map<String, dynamic>
          ? CommunityInfo.fromJson(json['community'] as Map<String, dynamic>)
          : null,
    );
  }
}

class AuthPayload {
  final String token;
  final AuthUser user;

  AuthPayload({required this.token, required this.user});

  factory AuthPayload.fromJson(Map<String, dynamic> json) {
    return AuthPayload(
      token: (json['token'] ?? '').toString(),
      user: AuthUser.fromJson((json['user'] ?? <String, dynamic>{}) as Map<String, dynamic>),
    );
  }
}

class ChatMessage {
  final String id;
  final String senderName;
  final String role;
  final String content;
  final String createdAt;
  final String? senderUserId;

  ChatMessage({
    required this.id,
    required this.senderName,
    required this.role,
    required this.content,
    required this.createdAt,
    this.senderUserId,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: (json['id'] ?? '').toString(),
      senderName: (json['sender_name'] ?? '').toString(),
      role: (json['role'] ?? '').toString(),
      content: (json['content'] ?? '').toString(),
      createdAt: (json['created_at'] ?? '').toString(),
      senderUserId: json['sender_user_id']?.toString(),
    );
  }
}

class AssistantAskResult {
  final ChatMessage userMessage;
  final ChatMessage assistantMessage;

  AssistantAskResult({required this.userMessage, required this.assistantMessage});

  factory AssistantAskResult.fromJson(Map<String, dynamic> json) {
    return AssistantAskResult(
      userMessage: ChatMessage.fromJson(
        (json['user_message'] ?? <String, dynamic>{}) as Map<String, dynamic>,
      ),
      assistantMessage: ChatMessage.fromJson(
        (json['assistant_message'] ?? <String, dynamic>{}) as Map<String, dynamic>,
      ),
    );
  }
}

class IncidentItem {
  final String id;
  final String title;
  final String description;
  final String status;
  final String priority;
  final String createdAt;

  IncidentItem({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    required this.priority,
    required this.createdAt,
  });

  factory IncidentItem.fromJson(Map<String, dynamic> json) {
    return IncidentItem(
      id: (json['id'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      description: (json['description'] ?? '').toString(),
      status: (json['status'] ?? '').toString(),
      priority: (json['priority'] ?? '').toString(),
      createdAt: (json['created_at'] ?? '').toString(),
    );
  }
}

class ShelterItem {
  final String id;
  final String name;
  final String address;
  final int capacity;
  final int currentOccupancy;
  final String status;

  ShelterItem({
    required this.id,
    required this.name,
    required this.address,
    required this.capacity,
    required this.currentOccupancy,
    required this.status,
  });

  factory ShelterItem.fromJson(Map<String, dynamic> json) {
    return ShelterItem(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      address: (json['address'] ?? '').toString(),
      capacity: (json['capacity'] ?? 0) is num
          ? (json['capacity'] as num).toInt()
          : int.tryParse((json['capacity'] ?? '0').toString()) ?? 0,
      currentOccupancy: (json['current_occupancy'] ?? 0) is num
          ? (json['current_occupancy'] as num).toInt()
          : int.tryParse((json['current_occupancy'] ?? '0').toString()) ?? 0,
      status: (json['status'] ?? '').toString(),
    );
  }
}

class CheckinSummary {
  final int total;
  final Map<String, int> byStatus;
  final String latestCheckinAt;

  CheckinSummary({
    required this.total,
    required this.byStatus,
    required this.latestCheckinAt,
  });

  factory CheckinSummary.fromJson(Map<String, dynamic> json) {
    final dynamic raw = json['by_status'];
    final map = <String, int>{};
    if (raw is Map) {
      raw.forEach((key, value) {
        map[key.toString()] = value is num ? value.toInt() : int.tryParse('$value') ?? 0;
      });
    }
    return CheckinSummary(
      total: (json['total'] ?? 0) is num
          ? (json['total'] as num).toInt()
          : int.tryParse((json['total'] ?? '0').toString()) ?? 0,
      byStatus: map,
      latestCheckinAt: (json['latest_checkin_at'] ?? '').toString(),
    );
  }
}

double _asDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse((value ?? '').toString()) ?? 0;
}
