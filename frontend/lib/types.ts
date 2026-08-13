export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  plan: string;
  avatar_seed: string;
}

export interface StageState {
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  notes: string;
}

export interface StageDef {
  id: string;
  name: string;
  phase: string;
  desc: string;
}

export interface Project {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  topic: string;
  category: string;
  language: string;
  tone: string;
  target_duration: number;
  status: string;
  progress: number;
  current_stage: string;
  stages: Record<string, StageState>;
  outputs: Record<string, any>;
  characters: any[];
  environments: any[];
  settings: Record<string, any>;
  created_at: string | null;
  updated_at: string | null;
}

export interface PipelineStatus {
  project_id: string;
  status: string;
  progress: number;
  current_stage: string;
  running: boolean;
  stages: Record<string, StageState>;
}

export interface RenderClip {
  id: string;
  scene_id: string;
  clip_ref: string;
  provider: string;
  status: string;
  score: number | null;
  prompt: string;
  file_url: string;
  thumb_url: string;
  duration_s: number;
  width: number;
  height: number;
  error: string;
  quality: any;
}

export interface RenderJob {
  id: string;
  project_id: string;
  scene_label: string;
  model: string;
  resolution: string;
  fps: number;
  status: string;
  progress: number;
  priority: number;
  error: string;
  duration_s: number;
  final_url: string;
  assembled_at: string | null;
  audio_report: any;
  clips: RenderClip[];
  created_at: string | null;
  finished_at: string | null;
}

export interface ProviderSetting {
  id: string;
  name: string;
  kind: "video" | "llm" | "tts";
  configured: boolean;
  source: "db" | "env" | "none";
  last4: string;
  env_configured: boolean;
}

export interface AnalyticsOverview {
  totals: {
    projects: number;
    published: number;
    renders_completed: number;
    views: number;
    watch_time_min: number;
    revenue_usd: number;
    ai_credits_used: number;
  };
  trend: { day: string; views: number; watch_min: number }[];
  retention: number[];
  platforms: { platform: string; status: string; url: string; published_at: string | null }[];
}

export interface CharacterItem {
  id: string;
  name: string;
  archetype: string;
  description: string;
  traits: string[];
  voice: any;
  expressions: string[];
  wardrobe: string[];
  palette: string[];
  is_shared: boolean;
}

export interface EnvironmentItem {
  id: string;
  name: string;
  category: string;
  description: string;
  lighting: any;
  weather: string[];
  palette: string[];
  is_shared: boolean;
}
