import { useEffect, useRef, useState } from "react";
import CloseIcon from "@mui/icons-material/Close";
import SendIcon from "@mui/icons-material/Send";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import {
  Box,
  Chip,
  CircularProgress,
  Fab,
  IconButton,
  LinearProgress,
  TextField,
  Typography,
} from "@mui/material";
import type { InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AI_SUGGESTED_QUESTIONS, isWebGpuSupported, type AiChatMessage } from "../services/aiAssistantContent";

type Status = "idle" | "unsupported" | "loading" | "ready" | "generating" | "error";

const PANEL_WIDTH = 360;

export default function AiAssistantWidget() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [messages, setMessages] = useState<AiChatMessage[]>([]);
  const [input, setInput] = useState("");
  const engineRef = useRef<MLCEngine | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight });
  }, [messages, status]);

  async function ensureEngineLoaded() {
    if (engineRef.current) return engineRef.current;
    setStatus("loading");
    setErrorMessage("");
    try {
      const supported = await isWebGpuSupported();
      if (!supported) {
        setStatus("unsupported");
        return null;
      }
      const { getOrCreateEngine } = await import("../services/aiAssistant");
      const engine = await getOrCreateEngine((report: InitProgressReport) => {
        setProgress(report.progress);
        setProgressText(report.text);
      });
      engineRef.current = engine;
      setStatus("ready");
      return engine;
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "No se pudo inicializar el asistente local.");
      return null;
    }
  }

  function handleOpen() {
    setOpen(true);
    if (status === "idle") {
      void ensureEngineLoaded();
    }
  }

  async function handleSend(question?: string) {
    const text = (question ?? input).trim();
    if (!text || status !== "ready") return;

    const nextHistory: AiChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(nextHistory);
    setInput("");
    setStatus("generating");

    const engine = engineRef.current;
    if (!engine) {
      setStatus("error");
      setErrorMessage("El asistente todavía no está listo.");
      return;
    }

    try {
      const { streamAssistantReply } = await import("../services/aiAssistant");
      let reply = "";
      setMessages([...nextHistory, { role: "assistant", content: "" }]);
      for await (const delta of streamAssistantReply(engine, nextHistory)) {
        reply += delta;
        setMessages([...nextHistory, { role: "assistant", content: reply }]);
      }
      setStatus("ready");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "error desconocido";
      setMessages([
        ...nextHistory,
        { role: "assistant", content: `Hubo un error generando la respuesta (${detail}). Probá de nuevo.` },
      ]);
      setStatus("ready");
    }
  }

  function handleRetry() {
    engineRef.current = null;
    setStatus("idle");
    void ensureEngineLoaded();
  }

  return (
    <>
      <Fab
        color="primary"
        onClick={() => (open ? setOpen(false) : handleOpen())}
        sx={{
          position: "fixed",
          bottom: 24,
          right: 24,
          zIndex: 1300,
          boxShadow: "0 4px 20px rgba(255, 107, 0, 0.4)",
        }}
        aria-label="Asistente IA"
        title="Asistente IA"
      >
        {open ? <CloseIcon /> : <SmartToyOutlinedIcon />}
      </Fab>

      {open && (
        <Box
          sx={{
            position: "fixed",
            bottom: 96,
            right: 24,
            width: PANEL_WIDTH,
            maxWidth: "calc(100vw - 32px)",
            height: 520,
            maxHeight: "70vh",
            zIndex: 1299,
            bgcolor: "#0F1117",
            border: "1px solid #1E2028",
            borderRadius: "12px",
            boxShadow: "0 16px 48px rgba(0, 0, 0, 0.6)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <Box
            sx={{
              px: 2,
              py: 1.5,
              borderBottom: "1px solid #1E2028",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: "0.95rem", color: "#E8E9EB" }}>
                Asistente IA
              </Typography>
              <Typography sx={{ fontSize: "0.68rem", color: "#6B7280" }}>
                IA local · las respuestas se generan en tu dispositivo
              </Typography>
            </Box>
            <IconButton size="small" onClick={() => setOpen(false)} sx={{ color: "#6B7280" }}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Body */}
          <Box ref={scrollRef} sx={{ flex: 1, overflowY: "auto", p: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
            {status === "unsupported" && (
              <Typography sx={{ fontSize: "0.85rem", color: "#8B92A7" }}>
                El asistente IA local requiere un navegador y dispositivo compatibles con WebGPU.
              </Typography>
            )}

            {status === "loading" && (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1 }}>
                <Typography sx={{ fontSize: "0.85rem", color: "#8B92A7" }}>
                  Preparando el asistente local. La primera carga puede tardar unos minutos porque el
                  modelo se descarga en este dispositivo.
                </Typography>
                <LinearProgress
                  variant={progress > 0 ? "determinate" : "indeterminate"}
                  value={Math.round(progress * 100)}
                />
                {progressText && (
                  <Typography sx={{ fontSize: "0.72rem", color: "#6B7280" }}>{progressText}</Typography>
                )}
              </Box>
            )}

            {status === "error" && (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                <Typography sx={{ fontSize: "0.85rem", color: "#F87171" }}>
                  No se pudo inicializar el asistente local{errorMessage ? `: ${errorMessage}` : "."}
                </Typography>
                <Chip label="Reintentar" onClick={handleRetry} size="small" sx={{ alignSelf: "flex-start" }} />
              </Box>
            )}

            {(status === "ready" || status === "generating") && messages.length === 0 && (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                <Typography sx={{ fontSize: "0.85rem", color: "#8B92A7" }}>
                  Asistente listo. Preguntame cómo usar CotizaLaser.
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                  {AI_SUGGESTED_QUESTIONS.map((q) => (
                    <Chip key={q} label={q} size="small" onClick={() => void handleSend(q)} sx={{ fontSize: "0.72rem" }} />
                  ))}
                </Box>
              </Box>
            )}

            {messages.map((m, i) => (
              <Box
                key={i}
                sx={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  bgcolor: m.role === "user" ? "rgba(255, 107, 0, 0.15)" : "#171922",
                  border: "1px solid",
                  borderColor: m.role === "user" ? "rgba(255, 107, 0, 0.3)" : "#1E2028",
                  borderRadius: "10px",
                  px: 1.5,
                  py: 1,
                }}
              >
                <Typography sx={{ fontSize: "0.85rem", color: "#E8E9EB", whiteSpace: "pre-wrap" }}>
                  {m.content || (status === "generating" && i === messages.length - 1 ? "…" : "")}
                </Typography>
              </Box>
            ))}

            {status === "generating" && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CircularProgress size={12} />
                <Typography sx={{ fontSize: "0.72rem", color: "#6B7280" }}>Generando respuesta…</Typography>
              </Box>
            )}
          </Box>

          {/* Footer */}
          <Box sx={{ p: 1.5, borderTop: "1px solid #1E2028", display: "flex", gap: 1 }}>
            <TextField
              size="small"
              fullWidth
              placeholder="Escribí tu pregunta…"
              value={input}
              disabled={status !== "ready"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
            />
            <IconButton
              color="primary"
              disabled={status !== "ready" || !input.trim()}
              onClick={() => void handleSend()}
            >
              <SendIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>
      )}
    </>
  );
}
