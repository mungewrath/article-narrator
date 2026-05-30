"use client";

import { AppBar, Toolbar, Typography, Button } from "@mui/material";
import { useAuth } from "react-oidc-context";

export const Header = () => {
  const auth = useAuth();

  const handleLogout = async () => {
    try {
      await auth.removeUser();
      const logoutUrl = `https://${process.env.NEXT_PUBLIC_COGNITO_DOMAIN}/logout?client_id=${process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID}&response_type=code&redirect_uri=${encodeURIComponent(process.env.NEXT_PUBLIC_COGNITO_REDIRECT as string)}&logout_uri=${encodeURIComponent(process.env.NEXT_PUBLIC_COGNITO_REDIRECT as string)}`;
      window.location.replace(logoutUrl);
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  return (
    <AppBar position="static" sx={{ bgcolor: "background.paper" }}>
      <Toolbar>
        <Typography variant="h6" component="h1" sx={{ flexGrow: 1 }}>
          Article Narrator
        </Typography>
        {auth.isLoading && <Typography sx={{ mr: 2, color: "text.secondary" }}>Loading...</Typography>}
        {auth.isAuthenticated ? (
          <Button color="inherit" onClick={handleLogout}>
            Sign out
          </Button>
        ) : (
          <Button color="inherit" onClick={() => auth.signinRedirect()}>
            Sign in
          </Button>
        )}
      </Toolbar>
    </AppBar>
  );
};
