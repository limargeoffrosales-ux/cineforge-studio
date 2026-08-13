"use client";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MessageSquare, Send, X, Clapperboard } from "lucide-react";
import { api } from "@/lib/api";
import { useUi } from "@/lib/store";

export function ChatPanel({ projectId }: { projectId?: string }) {
  const open = useUi((s) => s.chatOpen);
  const setOpen = useUi((s) => s.setChatOpen);
  const [messages, setMessages] = useState<{ role: "user" | "ai"; text: string }[]>([
    {
      role: "ai",
      text: "I'm your AI production director. Ask me about any stage — research, script, storyboard, renders, publishing — or tell me what to do next.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await api("/chat", { method: "POST", body: { message: text, project_id: projectId } });
      setMessages((m) => [...m, { role: "ai", text: res.reply }]);
    } catch {
      setMessages((m) => [...m, { role: "ai", text: "The director's console hiccuped — try again in a moment." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 24, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 24, scale: 0.97 }}
          transition={{ duration: 0.18 }}
          className="fixed bottom-5 right-5 z-50 flex h-[520px] w-[380px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-white/10 bg-ink-900 shadow-2xl"
        >
          <div className="flex items-center justify-between border-b border-white/8 bg-ink-850 px-4 py-3">
            <div className="flex items-center gap-2.5">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-gold-400 to-amber-600 text-ink-950">
                <Clapperboard className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-semibold text-zinc-100">AI Director</div>
                <div className="text-[11px] text-emerald-400">● online</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-zinc-500 hover:bg-white/10 hover:text-zinc-200">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                    m.role === "user"
                      ? "rounded-br-sm bg-gold-400 text-ink-950"
                      : "rounded-bl-sm border border-white/8 bg-ink-850 text-zinc-300"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-white/8 bg-ink-850 px-3.5 py-2.5 text-[13px] text-zinc-500">
                  <span className="animate-pulse">Thinking…</span>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-white/8 p-3">
            <div className="flex items-center gap-2">
              <input
                className="input !rounded-full !py-2"
                placeholder="Ask the director anything…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
              />
              <button onClick={send} disabled={busy || !input.trim()} className="btn-primary !rounded-full !p-2.5">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ChatHint() {
  const setOpen = useUi((s) => s.setChatOpen);
  return (
    <button
      onClick={() => setOpen(true)}
      className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-400 transition hover:bg-white/10 xl:flex"
    >
      <MessageSquare className="h-3.5 w-3.5 text-gold-400" /> Ask the AI Director
    </button>
  );
}
