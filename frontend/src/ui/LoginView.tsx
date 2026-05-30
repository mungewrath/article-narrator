"use client";

import { Box, Button, Card, CardContent, Typography } from "@mui/material";
import { useAuth } from "react-oidc-context";

export function LoginView() {
  const auth = useAuth();

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        p: 2,
      }}
    >
      <Card sx={{ maxWidth: 440, width: "100%", textAlign: "center" }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" component="h1" gutterBottom>
            Article Narrator
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Submit articles for podcast generation
          </Typography>
          {auth.error && (
            <Typography variant="body2" color="error" sx={{ mb: 1.5 }}>
              {auth.error.message}
            </Typography>
          )}
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => auth.signinRedirect()}
          >
            Sign in
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
