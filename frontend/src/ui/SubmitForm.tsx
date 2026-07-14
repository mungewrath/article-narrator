"use client";

import { useState } from "react";
import { useAuth } from "react-oidc-context";
import {
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  TextField,
  TextareaAutosize,
  Typography,
  Alert,
} from "@mui/material";

const VOICES = [
  { id: "tiernan", label: "Tiernan" },
  { id: "alton", label: "Alton" },
];

type InputMode = "url" | "text";

const TEXT_MAX_CHARS = 200000;

export function SubmitForm() {
  const auth = useAuth();
  const [mode, setMode] = useState<InputMode>("url");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [voice, setVoice] = useState("tiernan");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pasting, setPasting] = useState(false);

  const handlePaste = async () => {
    setError("");
    setSuccess("");
    setPasting(true);
    try {
      const clipText = await navigator.clipboard.readText();
      if (mode === "url") {
        setUrl(clipText);
      } else {
        setText((prev) => prev + clipText);
      }
    } catch {
      setError(
        "Could not read from clipboard. Make sure you've allowed clipboard access."
      );
    } finally {
      setPasting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    const token = auth.user?.id_token;
    if (!token) {
      setError("Not authenticated");
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl) {
      setError("API endpoint not configured");
      return;
    }

    const basePayload = {
      job_id: crypto.randomUUID(),
      submitted_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      voice,
    };

    let payload: Record<string, string>;

    if (mode === "url") {
      const trimmed = url.trim();
      if (!trimmed) return;
      payload = { ...basePayload, url: trimmed };
    } else {
      const trimmedText = text.trim();
      const trimmedTitle = title.trim();
      if (!trimmedText) return;
      if (!trimmedTitle) {
        setError("Title is required when pasting text");
        return;
      }
      if (trimmedText.length > TEXT_MAX_CHARS) {
        setError(`Text exceeds maximum of ${TEXT_MAX_CHARS.toLocaleString()} characters`);
        return;
      }
      payload = { ...basePayload, text: trimmedText, title: trimmedTitle };
    }

    setSubmitting(true);

    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const respText = await res.text();
        throw new Error(respText || res.statusText);
      }

      await res.json();
      setSuccess("Submitted successfully. The article will be processed shortly.");
      setUrl("");
      setText("");
      setTitle("");
    } catch (err) {
      setError(
        `Submission failed: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
      <Card sx={{ maxWidth: 480, width: "100%" }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            Submit an Article
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Paste a link or raw text to generate a podcast episode.
          </Typography>

          <ButtonGroup fullWidth sx={{ mb: 2 }} size="small">
            <Button
              variant={mode === "url" ? "contained" : "outlined"}
              onClick={() => setMode("url")}
            >
              URL
            </Button>
            <Button
              variant={mode === "text" ? "contained" : "outlined"}
              onClick={() => setMode("text")}
            >
              Paste Text
            </Button>
          </ButtonGroup>

          <Box component="form" onSubmit={handleSubmit} noValidate>
            {mode === "url" ? (
              <TextField
                label="Article URL"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                required
                fullWidth
                size="small"
                sx={{ mb: 2 }}
                InputProps={{
                  endAdornment: (
                    <Box
                      component="span"
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        pr: 0.5,
                      }}
                    >
                      <Button
                        size="small"
                        disabled={pasting}
                        onClick={handlePaste}
                        sx={{ minWidth: 0, p: "2px 6px", fontSize: "0.75rem" }}
                      >
                        {pasting ? "..." : "Paste"}
                      </Button>
                    </Box>
                  ),
                }}
              />
            ) : (
              <>
                <TextField
                  label="Title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Article title"
                  required
                  fullWidth
                  size="small"
                  sx={{ mb: 2 }}
                />
                <Box sx={{ mb: 2, position: "relative" }}>
                  <TextareaAutosize
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Paste article text here..."
                    minRows={6}
                    maxRows={16}
                    style={{
                      width: "100%",
                      padding: "12px",
                      fontFamily: "inherit",
                      fontSize: "0.875rem",
                      lineHeight: 1.5,
                      border: "1px solid rgba(0,0,0,0.23)",
                      borderRadius: "4px",
                      resize: "vertical",
                      boxSizing: "border-box",
                    }}
                  />
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      mt: 0.5,
                    }}
                  >
                    <Button
                      size="small"
                      disabled={pasting}
                      onClick={handlePaste}
                      sx={{ minWidth: 0, p: "2px 6px", fontSize: "0.75rem" }}
                    >
                      {pasting ? "..." : "Paste from clipboard"}
                    </Button>
                    <Typography
                      variant="caption"
                      color={
                        text.length > TEXT_MAX_CHARS ? "error" : "text.secondary"
                      }
                    >
                      {text.length.toLocaleString()} / {TEXT_MAX_CHARS.toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
              </>
            )}

            <FormControl sx={{ mb: 2 }}>
              <FormLabel sx={{ fontSize: "0.875rem", color: "text.secondary" }}>
                Voice
              </FormLabel>
              <RadioGroup
                row
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
              >
                {VOICES.map((v) => (
                  <FormControlLabel
                    key={v.id}
                    value={v.id}
                    control={<Radio size="small" />}
                    label={v.label}
                  />
                ))}
              </RadioGroup>
            </FormControl>
            {error && (
              <Alert severity="error" sx={{ mb: 1.5, py: 0, fontSize: "0.85rem" }}>
                {error}
              </Alert>
            )}
            {success && (
              <Alert
                severity="success"
                sx={{ mb: 1.5, py: 0, fontSize: "0.85rem" }}
              >
                {success}
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={submitting}
            >
              {submitting ? "Submitting..." : "Submit"}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
