export interface User {
  id: string;
  email: string;
  username: string;
  role: 'admin' | 'analyst' | 'viewer';
  avatar?: string;
  created_at: string;
  last_login?: string;
}

export interface Case {
  id: string;
  title: string;
  description: string;
  status: 'open' | 'investigating' | 'closed' | 'archived';
  priority: 'low' | 'medium' | 'high' | 'critical';
  created_by: string;
  assigned_to: string[];
  tags: string[];
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface Account {
  id: string;
  case_id: string;
  platform: string;
  username: string;
  display_name?: string;
  profile_url?: string;
  avatar_url?: string;
  bio?: string;
  followers?: number;
  following?: number;
  post_count?: number;
  verified?: boolean;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
  credibility_score?: number;
  influence_score?: number;
}

export interface Post {
  id: string;
  case_id: string;
  account_id: string;
  platform: string;
  author_username?: string;
  author_display?: string;
  author_profile?: string;
  content: string;
  post_url?: string;
  media_urls?: string[];
  likes?: number;
  shares?: number;
  comments?: number;
  posted_at: string;
  collected_at: string;
  sentiment?: 'positive' | 'negative' | 'neutral' | 'mixed';
  topics?: string[];
  metadata?: Record<string, unknown>;
}

export interface Claim {
  id: string;
  case_id: string;
  text: string;
  source_account_id?: string;
  source_post_id?: string;
  category: 'fact' | 'opinion' | 'misinformation' | 'disinformation' | 'unverified';
  confidence: number;
  evidence_count: number;
  status: 'pending' | 'verified' | 'debunked' | 'contested';
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface Evidence {
  id: string;
  case_id: string;
  claim_id?: string;
  type: 'screenshot' | 'archive' | 'text' | 'image' | 'video' | 'document' | 'link';
  title: string;
  description?: string;
  url?: string;
  file_path?: string;
  hash?: string;
  tags: string[];
  added_by: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  type: 'account' | 'post' | 'claim' | 'evidence' | 'hashtag' | 'url';
  label: string;
  data: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'posted_by' | 'supports' | 'refutes' | 'mentions' | 'shares' | 'related_to';
  weight?: number;
  metadata?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineEvent {
  id: string;
  case_id: string;
  type: 'account_created' | 'post_collected' | 'claim_made' | 'evidence_added' | 'status_change' | 'analysis_update';
  title: string;
  description?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  related_ids?: {
    account_id?: string;
    post_id?: string;
    claim_id?: string;
    evidence_id?: string;
  };
}

export interface AnalysisResult {
  id: string;
  case_id: string;
  type: 'sentiment' | 'network' | 'temporal' | 'topic' | 'credibility';
  results: Record<string, unknown>;
  created_at: string;
}

export interface Report {
  id: string;
  case_id: string;
  title: string;
  content: string;
  format: 'markdown' | 'html' | 'pdf';
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}
