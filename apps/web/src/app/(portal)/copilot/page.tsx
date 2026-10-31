"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Banknote,
  Clock3,
  Compass,
  FileSearch,
  Loader2,
  MessageSquareText,
  Plus,
  Send,
  ShieldCheck,
  TrendingUp,
  X,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn, formatCurrency } from "@/lib/utils";
import { getErrorMessage } from "@/lib/api-client";
import { copilotService } from "@/services/copilot-service";
import type {
  CopilotClaimResult,
  CopilotConfirmation,
  CopilotConversation,
  CopilotEvidence,
  CopilotMessage,
} from "@/types/copilot";

const SUGGESTIONS = [
  { label: "Top recovery opportunities", icon: TrendingUp },
  { label: "Show unpaid claims over KSh 50,000", icon: Banknote },
  { label: "Show pending appeals", icon: Clock3 },
  { label: "Which payer gives us the highest recovery rate?", icon: FileSearch },
  { label: "How much are we likely to recover this quarter?", icon: Compass },
];

function claimRows(output: unknown): CopilotClaimResult[] {
  if (!output || typeof output !== "object") return [];
  const value = output as { claims?: unknown };
  return Array.isArray(value.claims) ? (value.claims as CopilotClaimResult[]).slice(0, 5) : [];
}

function EvidenceLinks({ evidence }: { evidence: CopilotEvidence[] }) {
  if (!evidence.length) return null;
  return (
    <div className="mt-4 border-t pt-3">
      <p className="mb-2 text-[11px] font-semibold uppercase text-muted-foreground">Evidence</p>
      <div className="flex flex-wrap gap-2">
        {evidence.map((item, index) => (
          <Link
            key={`${item.path}-${index}`}
            href={item.path}
            className="inline-flex items-center gap-1 rounded-md border bg-background px-2.5 py-1.5 text-xs font-medium hover:border-primary/40 hover:text-primary"
          >
            {item.label}
            <ChevronRight className="h-3 w-3" />
          </Link>
        ))}
      </div>
    </div>
  );
}

function ResultRows({ rows }: { rows: CopilotClaimResult[] }) {
  if (!rows.length) return null;
  return (
    <div className="mt-4 overflow-hidden rounded-md border bg-background">
      {rows.map((claim) => {
        const id = claim.id ?? claim.claim_id;
        const amount = claim.estimated_recovery ?? claim.outstanding_amount ?? claim.billed_amount;
        return (
          <Link
            href={id ? `/claims/detail?id=${id}` : "/claims"}
            key={claim.claim_number}
            className="grid grid-cols-[1fr_auto] gap-4 border-b px-3 py-2.5 last:border-b-0 hover:bg-muted/50"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{claim.claim_number}</p>
              <p className="truncate text-xs text-muted-foreground">{claim.payer} · {claim.priority}</p>
            </div>
            {amount !== undefined && (
              <span className="self-center text-sm font-semibold tabular-nums">
                {formatCurrency(amount)}
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}

function MessageBubble({ message }: { message: CopilotMessage }) {
  const assistant = message.role === "assistant";
  const rows = claimRows(message.tool_output);
  return (
    <div className={cn("flex gap-3", assistant ? "justify-start" : "justify-end")}>
      {assistant && (
        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center border text-muted-foreground">
          <Compass className="h-4 w-4" strokeWidth={1.75} />
        </div>
      )}
      <div className={cn(
        "max-w-[760px] rounded-lg px-4 py-3 text-sm leading-6",
        assistant ? "w-full border bg-card" : "bg-primary text-primary-foreground",
      )}>
        <p className="whitespace-pre-wrap">{message.content}</p>
        {assistant && <ResultRows rows={rows} />}
        {assistant && <EvidenceLinks evidence={message.evidence ?? []} />}
        {assistant && message.navigation_path && (
          <Button asChild variant="outline" size="sm" className="mt-3">
            <Link href={message.navigation_path}>Open workspace <ArrowRight className="h-3.5 w-3.5" /></Link>
          </Button>
        )}
      </div>
    </div>
  );
}

export default function CopilotPage() {
  const [conversations, setConversations] = useState<CopilotConversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [confirmation, setConfirmation] = useState<CopilotConfirmation | null>(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function refreshConversations() {
    try {
      setConversations(await copilotService.listConversations());
    } catch {
      setConversations([]);
    }
  }

  useEffect(() => { void refreshConversations(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  async function openConversation(id: number) {
    setLoading(true);
    setError(null);
    setConfirmation(null);
    try {
      const detail = await copilotService.getConversation(id);
      setConversationId(id);
      setMessages(detail.messages);
      setSuggestedQuestions([]);
    } catch (err) {
      setError(getErrorMessage(err, "Unable to open this conversation."));
    } finally {
      setLoading(false);
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setConfirmation(null);
    setSuggestedQuestions([]);
    setError(null);
    setInput("");
  }

  async function send(text: string) {
    const value = text.trim();
    if (!value || loading) return;
    setInput("");
    setError(null);
    setMessages((current) => [...current, {
      id: -Date.now(), role: "user", content: value, tool_name: null, tool_input: null,
      tool_output: null, evidence: null, navigation_path: null, created_at: new Date().toISOString(),
    }]);
    setLoading(true);
    try {
      const response = await copilotService.chat(value, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, response.message]);
      setConfirmation(response.confirmation);
      setSuggestedQuestions(response.suggested_questions);
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, "Atlas could not complete that request."));
    } finally {
      setLoading(false);
    }
  }

  async function confirmAction() {
    if (!confirmation || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await copilotService.confirm(confirmation.token);
      setMessages((current) => [...current, response.message]);
      setConfirmation(null);
    } catch (err) {
      setError(getErrorMessage(err, "The action could not be confirmed."));
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <Header title="Atlas Copilot" />
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 shrink-0 border-r bg-background xl:flex xl:flex-col">
          <div className="p-3">
            <Button onClick={newConversation} variant="outline" className="w-full justify-start">
              <Plus className="h-4 w-4" /> New conversation
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
            <p className="px-2 pb-2 text-[11px] font-semibold uppercase text-muted-foreground">Recent</p>
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => void openConversation(conversation.id)}
                className={cn(
                  "mb-1 flex w-full items-start gap-2 rounded-md px-2.5 py-2 text-left text-sm",
                  conversationId === conversation.id ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <MessageSquareText className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="line-clamp-2">{conversation.title.replaceAll("$", "KSh ")}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-4 py-6 sm:px-6">
              {messages.length === 0 && !loading ? (
                <div className="my-auto py-10">
                  <div className="mb-8 flex items-center gap-3">
                    <Compass className="h-5 w-5 text-primary" strokeWidth={1.75} />
                    <div>
                      <h2 className="text-lg font-semibold">Revenue intelligence</h2>
                      <p className="text-sm text-muted-foreground">What needs attention today?</p>
                    </div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {SUGGESTIONS.map(({ label, icon: Icon }) => (
                      <button
                        key={label}
                        onClick={() => void send(label)}
                        className="flex min-h-14 items-center gap-3 rounded-md border bg-background px-4 py-3 text-left text-sm font-medium hover:border-primary/30 hover:bg-muted/30"
                      >
                        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>{label}</span>
                        <ChevronRight className="ml-auto h-4 w-4 shrink-0 text-muted-foreground" />
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-5">
                  {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
                  {!loading && suggestedQuestions.length > 0 && (
                    <div className="ml-10 flex flex-wrap gap-2" aria-label="Suggested follow-up questions">
                      {suggestedQuestions.slice(0, 4).map((question) => (
                        <button
                          key={question}
                          type="button"
                          onClick={() => void send(question)}
                          className="rounded-md border bg-background px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  )}
                  {loading && (
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" /> Reviewing Atlas records…
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
          </div>

          <div className="border-t bg-background px-4 py-3 sm:px-6">
            <div className="mx-auto max-w-4xl">
              {confirmation && (
                <div className="mb-3 flex flex-col gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 sm:flex-row sm:items-center">
                  <ShieldCheck className="h-5 w-5 shrink-0 text-amber-700" />
                  <p className="flex-1 text-sm font-medium text-amber-950">{confirmation.summary}</p>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => void confirmAction()} disabled={loading}>
                      <Check className="h-4 w-4" /> Confirm
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setConfirmation(null)} disabled={loading}>
                      <X className="h-4 w-4" /> Cancel
                    </Button>
                  </div>
                </div>
              )}
              {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
              <form onSubmit={submit} className="flex items-end gap-2">
                <Textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit(event);
                    }
                  }}
                  placeholder="Ask about claims, denials, appeals, or recovery…"
                  className="min-h-11 max-h-32 resize-none"
                  disabled={loading}
                />
                <Button type="submit" size="icon" disabled={!input.trim() || loading} title="Send">
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}