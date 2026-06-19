"use client";

import { useState } from "react";
import { useAuth } from "react-oidc-context";
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  FormLabel,
  InputAdornment,
  Radio,
  RadioGroup,
  TextField,
  Typography,
  Alert,
} from "@mui/material";

const VOICES = [
  { id: "tiernan", label: "Tiernan" },
  { id: "alton", label: "Alton" },
];

export function SubmitForm() {
  const auth = useAuth();
  const [url, setUrl] = useState("");
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
      const text = await navigator.clipboard.readText();
      setUrl(text);
    } catch {
      setError("Could not read from clipboard. Make sure you've allowed clipboard access.");
    } finally {
      setPasting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    const trimmed = url.trim();
    if (!trimmed) return;

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

    setSubmitting(true);

    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          url: trimmed,
          job_id: crypto.randomUUID(),
          submitted_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
          voice,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }

      await res.json();
      setSuccess("Submitted successfully. The article will be processed shortly.");
      setUrl("");
    } catch (err) {
      setError(`Submission failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
      <Card sx={{ maxWidth: 480, width: "100%" }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            Submit a URL
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Paste a link to an article to generate a podcast episode.
          </Typography>
          <Box component="form" onSubmit={handleSubmit} noValidate>
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
                  <InputAdornment position="end">
                    <Button
                      size="small"
                      disabled={pasting}
                      onClick={handlePaste}
                      sx={{ minWidth: 0, p: "2px 6px", fontSize: "0.75rem" }}
                    >
                      {pasting ? "..." : "Paste"}
                    </Button>
                  </InputAdornment>
                ),
              }}
            />
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
              <Alert severity="success" sx={{ mb: 1.5, py: 0, fontSize: "0.85rem" }}>
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
