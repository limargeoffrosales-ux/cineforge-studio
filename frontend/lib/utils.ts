export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

export function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "—";
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// deterministic pastel from a seed (avatar fallback)
const PALETTES = [
  ["#f5b301", "#3a2e06"],
  ["#8b5cf6", "#1e1533"],
  ["#38bdf8", "#0c2735"],
  ["#34d399", "#0b2e20"],
  ["#fb7185", "#351018"],
];

export function paletteFor(seed: string): string[] {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTES[h % PALETTES.length];
}

export const STAGE_ICONS: Record<string, string> = {
  idea: "💡",
  research: "🔎",
  script: "✍️",
  storyboard: "🎬",
  scene_planning: "📋",
  character_design: "🧑‍🎤",
  environment_design: "🌏",
  shot_planning: "🎥",
  video_generation: "🖥️",
  voice_generation: "🎙️",
  sound_design: "🔊",
  music: "🎵",
  editing: "✂️",
  motion_graphics: "✨",
  subtitles: "💬",
  thumbnail: "🖼️",
  seo: "📈",
  publishing: "🚀",
};

export const CATEGORIES = [
  { id: "youtube", label: "YouTube" },
  { id: "tiktok", label: "TikTok" },
  { id: "instagram", label: "Instagram" },
  { id: "documentary", label: "Documentary" },
  { id: "education", label: "Educational" },
  { id: "review", label: "Product Review" },
  { id: "tutorial", label: "Tutorial" },
  { id: "explainer", label: "Explainer" },
  { id: "news", label: "News Summary" },
  { id: "storytelling", label: "Storytelling" },
];

export const TONES = ["cinematic", "energetic", "educational", "inspirational", "professional", "humorous"];

export const LANGUAGES = [
  { id: "en", label: "English" },
  { id: "tl", label: "Filipino" },
  { id: "es", label: "Spanish" },
  { id: "ja", label: "Japanese" },
  { id: "ko", label: "Korean" },
  { id: "fr", label: "French" },
  { id: "de", label: "German" },
  { id: "zh", label: "Mandarin" },
];
