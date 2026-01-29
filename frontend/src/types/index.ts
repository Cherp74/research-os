// ============== Planning Types ==============

export interface PlanningData {
  originalQuery: string;
  understoodQuery: string;
  userModifiedQuery: string;
  selectedAngles: string[];
  customAngle: string;
  subQuestions: string[];
  userModifiedSubQuestions: string[];
}

// ============== Research Types ==============

export interface Source {
  id: string;
  url: string;
  title?: string;
  text?: string;
  content_hash: string;
  source_type: string;
  domain?: string;
  credibility_score: number;
  credibility_factors: Record<string, number>;
  word_count: number;
  has_citations: boolean;
  has_methodology: boolean;
  publish_date?: string;
  fetched_at: string;
}

export interface Claim {
  id: string;
  source_id: string;
  text: string;
  confidence: number;
  entities: string[];
  keywords: string[];
  verified: boolean;
  verification_method: string;
  verification_confidence: number;
  source_excerpt?: string;
  created_at: string;
}

export interface GraphNode {
  id: string;
  type: 'claim' | 'entity' | 'source';
  label: string;
  color: string;
  size: number;
  data: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  color: string;
  confidence: number;
  width: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ResearchSession {
  id: string;
  query: string;
  mode: string;
  phase: string;
  status: string;
  progress_percent: number;
  target_sources: number;
  source_count: number;
  claim_count: number;
  debate_rounds: number;
  final_report?: string;
  graph_data?: GraphData;
  started_at: string;
  completed_at?: string;
}

// ============== WebSocket Event Types ==============

export interface BaseEvent {
  type: string;
  session_id: string;
  timestamp: string;
}

export interface StatusEvent extends BaseEvent {
  type: 'status';
  phase: string;
  message: string;
  progress_percent: number;
}

export interface SourceEvent extends BaseEvent {
  type: 'source';
  source: Source;
}

export interface ClaimEvent extends BaseEvent {
  type: 'claim';
  claim: Claim;
  agent_name: string;
}

export interface GraphUpdateEvent extends BaseEvent {
  type: 'graph';
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DebateEvent extends BaseEvent {
  type: 'debate';
  round_number: number;
  agent_name: string;
  argument: string;
  confidence: number;
}

export interface ReportEvent extends BaseEvent {
  type: 'report';
  markdown: string;
  complete: boolean;
}

export interface ErrorEvent extends BaseEvent {
  type: 'error';
  message: string;
  details?: string;
}

export interface SessionCreatedEvent extends BaseEvent {
  type: 'session_created';
  query: string;
  mode: string;
}

export type ResearchEvent =
  | StatusEvent
  | SourceEvent
  | ClaimEvent
  | GraphUpdateEvent
  | DebateEvent
  | ReportEvent
  | ErrorEvent
  | SessionCreatedEvent;

// ============== Component Props ==============

export interface QueryBuilderProps {
  onSubmit: (query: string, mode: string, targetSources: number) => void;
  isResearching: boolean;
}

export interface ProgressTrackerProps {
  phase: string;
  message: string;
  progress: number;
}

export interface KnowledgeGraphProps {
  data: GraphData;
  onNodeClick?: (node: GraphNode) => void;
}

export interface SourceCardProps {
  source: Source;
}

export interface ClaimCardProps {
  claim: Claim;
  source?: Source;
}

export interface DebateViewProps {
  events: DebateEvent[];
}

export interface ReportViewerProps {
  markdown: string;
}
