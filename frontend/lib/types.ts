export interface Presentation {
  id: number
  title: string
  segment_count: number
}

export interface ReferenceAudioResponse {
  transcript: string
  coverage_pct: number
  language: string
  segments: number
}

export interface DegradationResponse {
  text: string
  blanked_indices: number[]
  level: number
}

export interface SessionResponse {
  session_id: number
}

export interface AttemptResult {
  transcript: string
  error_count: number
  hesitation_count: number
  error_ratio: number
  omitted: string[]
  substituted: [string, string][]
  hesitation_points: number[]
}

export interface ScheduleSegment {
  index: number
  score: number
  text: string
}

export interface ScheduleSummary {
  total_segments: number
  dominated: number
  pct_dominated: number
}

export interface ScheduleData {
  summary: ScheduleSummary
  repeat_segments: ScheduleSegment[]
}

export interface ReportSegment {
  index: number
  text: string
  attempts: number
  difficulty_score: number
}

export interface ReportSession {
  id: number
  level: number
  started_at: string
  mean_score: number | null
}

export interface ReportData {
  presentation_id: number
  title: string
  segments: ReportSegment[]
  sessions: ReportSession[]
}
