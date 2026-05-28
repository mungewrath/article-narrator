(function () {
  var COGNITO = window.COGNITO || { domain: "", clientId: "", region: "us-east-1" };
  var API_URL = window.API_URL || "";

  var TOKEN_KEY = "cognito_id_token";

  var loginView = document.getElementById("login-view");
  var dashboardView = document.getElementById("dashboard-view");
  var loginBtn = document.getElementById("login-btn");
  var logoutBtn = document.getElementById("logout-btn");
  var submitForm = document.getElementById("submit-form");
  var urlInput = document.getElementById("url-input");
  var submitError = document.getElementById("submit-error");
  var submitSuccess = document.getElementById("submit-success");
  var submitBtn = document.getElementById("submit-btn");

  function getCurrentUrl() {
    var path = window.location.pathname.replace(/\/$/, "");
    return window.location.protocol + "//" + window.location.host + path;
  }

  function cognitoLoginUrl() {
    var callback = encodeURIComponent(getCurrentUrl());
    return "https://" + COGNITO.domain + "/login?client_id=" + COGNITO.clientId
      + "&response_type=token&scope=openid&redirect_uri=" + callback;
  }

  function cognitoLogoutUrl() {
    var logoutUri = encodeURIComponent(getCurrentUrl());
    return "https://" + COGNITO.domain + "/logout?client_id=" + COGNITO.clientId
      + "&logout_uri=" + logoutUri;
  }

  function setView(name) {
    loginView.classList.toggle("hidden", name !== "login");
    dashboardView.classList.toggle("hidden", name !== "dashboard");
  }

  function getIdToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  function handleCallback() {
    var hash = window.location.hash;
    if (!hash || hash.indexOf("id_token=") === -1) return false;

    var params = {};
    hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var parts = kv.split("=");
      if (parts.length === 2) params[parts[0]] = parts[1];
    });

    if (params.id_token) {
      sessionStorage.setItem(TOKEN_KEY, params.id_token);
      window.location.hash = "";
      return true;
    }
    return false;
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    if (COGNITO.domain) {
      window.location.href = cognitoLogoutUrl();
    } else {
      setView("login");
    }
  }

  function showError(el, msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function hideError(el) {
    el.classList.add("hidden");
    el.textContent = "";
  }

  function hideSuccess(el) {
    el.classList.add("hidden");
    el.textContent = "";
  }

  loginBtn.addEventListener("click", function () {
    if (COGNITO.domain) {
      window.location.href = cognitoLoginUrl();
    } else {
      showError(document.getElementById("login-error"), "Cognito not configured");
    }
  });

  logoutBtn.addEventListener("click", logout);

  submitForm.addEventListener("submit", function (e) {
    e.preventDefault();
    hideError(submitError);
    hideSuccess(submitSuccess);

    var url = urlInput.value.trim();
    if (!url) return;

    var token = getIdToken();
    if (!token) {
      showError(submitError, "Not authenticated");
      return;
    }

    if (!API_URL) {
      showError(submitError, "API endpoint not configured");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";

    fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify({
        url: url,
        job_id: crypto.randomUUID(),
        submitted_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      }),
    })
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(t || r.statusText); });
        return r.json();
      })
      .then(function () {
        submitSuccess.textContent = "Submitted successfully. The article will be processed shortly.";
        submitSuccess.classList.remove("hidden");
        urlInput.value = "";
      })
      .catch(function (err) {
        showError(submitError, "Submission failed: " + err.message);
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit";
      });
  });

  if (handleCallback()) {
    setView("dashboard");
  } else if (getIdToken()) {
    setView("dashboard");
  } else {
    setView("login");
  }
})();
