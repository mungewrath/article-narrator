"use client";

import { AuthProvider } from "react-oidc-context";
import { Alert, Box, Typography } from "@mui/material";
import LocalStorageStateStore from "@/app/LocalStorageStateStore";
import { Header } from "@/app/Header";
import { LoginView } from "@/ui/LoginView";
import { SubmitForm } from "@/ui/SubmitForm";
import { useAuth } from "react-oidc-context";

function Dashboard() {
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <Typography color="text.secondary">Loading...</Typography>
      </Box>
    );
  }

  if (auth.error) {
    return <LoginView />;
  }

  if (!auth.isAuthenticated) {
    return <LoginView />;
  }

  return (
    <>
      <Header />
      <SubmitForm />
    </>
  );
}

function ConfigError({ label }: { label: string }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
      <Alert severity="warning">
        <Typography variant="body2">
          <strong>{label}</strong> is not configured. Set it in <code>.env.development</code> or the environment.
        </Typography>
      </Alert>
    </Box>
  );
}

export default function Home() {
  const authority = process.env.NEXT_PUBLIC_COGNITO_AUTHORITY;
  const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
  const redirectUri = process.env.NEXT_PUBLIC_COGNITO_REDIRECT;

  if (!authority) return <ConfigError label="NEXT_PUBLIC_COGNITO_AUTHORITY" />;
  if (!clientId) return <ConfigError label="NEXT_PUBLIC_COGNITO_CLIENT_ID" />;
  if (!redirectUri) return <ConfigError label="NEXT_PUBLIC_COGNITO_REDIRECT" />;

  const cognitoAuthConfig = {
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid",
    automaticSilentRenew: true,
    silent_redirect_uri: redirectUri,
    userStore: new LocalStorageStateStore(),
  };

  return (
    <AuthProvider {...cognitoAuthConfig}>
      <Dashboard />
    </AuthProvider>
  );
}
