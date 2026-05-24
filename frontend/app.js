// ── State ──────────────────────────────────────────────────────────────────
let currentToken = null;
let currentUser  = null;
let currentMode  = null;

const stats = { calls: 0, ok: 0, fail: 0 };

// ── DOM refs ──────────────────────────────────────────────────────────────
const logBox       = document.querySelector("#log");
const rpcLocked    = document.querySelector("#rpc-locked");
const rpcFields    = document.querySelector("#rpc-fields");
const dataField    = document.querySelector("#data-field");
const itemidField  = document.querySelector("#itemid-field");
const rpcMethodSel = document.querySelector("#rpc-method");

// ── Helpers ────────────────────────────────────────────────────────────────
function bump(key) {
  stats[key] += 1;
  document.querySelector(`#${key}`).textContent = stats[key];
}

function writeLog(lines) {
  logBox.textContent = lines.join("\n");
}

function setStep(prefix, name, state = "active") {
  document.querySelectorAll(`[data-step^="${prefix}"]`).forEach((step) => {
    step.classList.remove("active", "error");
    if (step.dataset.step === name) step.classList.add(state);
  });
}

function clearSteps(prefix) {
  document.querySelectorAll(`[data-step^="${prefix}"]`).forEach((step) => {
    step.classList.remove("active", "error");
  });
}

function showLoggedIn() {
  rpcLocked.style.display = "none";
  rpcFields.style.display = "";
}

// ── Tabs ───────────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`#tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// ── RPC method toggle (data vs item_id) ────────────────────────────────────
rpcMethodSel.addEventListener("change", () => {
  const m = rpcMethodSel.value;
  dataField.style.display   = m === "writeRecord" ? "" : "none";
  itemidField.style.display = m === "deleteItem"  ? "" : "none";
});

// ── Register ───────────────────────────────────────────────────────────────
document.querySelector("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.querySelector("#reg-username").value.trim();
  const password = document.querySelector("#reg-password").value;
  const mode     = document.querySelector("#reg-mode").value;
  const modeLabel = mode === "symmetric" ? "AES symmetric" : "RSA asymmetric";

  bump("calls");
  clearSteps("reg");
  setStep("reg", "reg-client", "active");
  writeLog([`Client: encrypting registration with ${modeLabel}`]);

  try {
    const res  = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, mode }),
    });
    const data = await res.json();

    if (data.ok) {
      setStep("reg", "reg-auth", "active");
      bump("ok");
      writeLog([
        `Client: encrypted registration (${modeLabel})`,
        `Auth Service: account '${data.message.username}' created`,
        "",
        JSON.stringify(data.message, null, 2),
      ]);
    } else {
      setStep("reg", "reg-auth", "error");
      bump("fail");
      writeLog([
        `Client: encrypted registration (${modeLabel})`,
        `Auth Service: ${data.error}`,
      ]);
    }
  } catch (err) {
    setStep("reg", "reg-auth", "error");
    bump("fail");
    writeLog([`Client: encrypted registration (${modeLabel})`, `Error: ${err.message}`]);
  }
});

// ── Login ──────────────────────────────────────────────────────────────────
document.querySelector("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.querySelector("#login-username").value.trim();
  const password = document.querySelector("#login-password").value;
  const mode     = document.querySelector("#login-mode").value;
  const modeLabel = mode === "symmetric" ? "AES symmetric" : "RSA asymmetric";

  bump("calls");
  clearSteps("login");
  setStep("login", "login-client", "active");
  writeLog([`Client: encrypting credentials with ${modeLabel}`]);

  try {
    const res  = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, mode, method: "getData" }),
    });
    const data = await res.json();

    if (data.ok) {
      setStep("login", "login-auth", "active");
      currentToken = data.token;
      currentUser  = username;
      currentMode  = mode;
      bump("ok");
      showLoggedIn();
      writeLog([
        `Client: encrypted credentials (${modeLabel})`,
        `Auth Service: token issued for '${username}'`,
        `Token: ${data.token.slice(0, 42)}...`,
        "",
        "Logged in! Switch to the RPC Calls tab.",
      ]);
    } else {
      setStep("login", "login-auth", "error");
      bump("fail");
      writeLog([
        `Client: encrypted credentials (${modeLabel})`,
        `Auth Service: ${data.error}`,
      ]);
    }
  } catch (err) {
    setStep("login", "login-auth", "error");
    bump("fail");
    writeLog([`Client: encrypting credentials (${modeLabel})`, `Error: ${err.message}`]);
  }
});

// ── Reset Password ────────────────────────────────────────────────────────
document.querySelector("#reset-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.querySelector("#reset-username").value.trim();
  const newPassword = document.querySelector("#reset-password").value;
  const mode = document.querySelector("#reset-mode").value;
  const modeLabel = mode === "symmetric" ? "AES symmetric" : "RSA asymmetric";

  bump("calls");
  clearSteps("reset");
  setStep("reset", "reset-client", "active");
  writeLog([`Client: encrypting reset request with ${modeLabel}`]);

  try {
    const res = await fetch("/api/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, new_password: newPassword, mode }),
    });
    const data = await res.json();

    if (data.ok) {
      setStep("reset", "reset-auth", "active");
      bump("ok");
      writeLog([
        `Client: encrypted reset request (${modeLabel})`,
        `Auth Service: password reset for '${data.message.username}'`,
        "",
        JSON.stringify(data.message, null, 2),
      ]);
    } else {
      setStep("reset", "reset-auth", "error");
      bump("fail");
      writeLog([
        `Client: encrypted reset request (${modeLabel})`,
        `Auth Service: ${data.error}`,
      ]);
    }
  } catch (err) {
    setStep("reset", "reset-auth", "error");
    bump("fail");
    writeLog([`Client: encrypted reset request (${modeLabel})`, `Error: ${err.message}`]);
  }
});

// ── RPC Call ───────────────────────────────────────────────────────────────
document.querySelector("#rpc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentToken) return;

  const method  = rpcMethodSel.value;
  const modeLabel = currentMode === "symmetric" ? "AES symmetric" : "RSA asymmetric";
  const body = { method, token: currentToken };

  if (method === "writeRecord") body.data    = document.querySelector("#rpc-data").value;
  if (method === "deleteItem")   body.item_id = document.querySelector("#rpc-item-id").value;

  bump("calls");
  clearSteps("rpc");
  setStep("rpc", "rpc-client", "active");
  writeLog([
    `Client: calling ${method}() (${modeLabel})`,
    "RPC Server: verifying token",
  ]);

  try {
    const res  = await fetch("/api/rpc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.ok) {
      setStep("rpc", "rpc-server", "active");
      bump("ok");
      writeLog([
        `Client: calling ${method}() (${modeLabel})`,
        "RPC Server: token verified",
        `RPC Server: ${method} complete`,
        "",
        JSON.stringify(data.result, null, 2),
      ]);
    } else {
      setStep("rpc", "rpc-server", "error");
      bump("fail");
      writeLog([
        `Client: calling ${method}() (${modeLabel})`,
        `RPC Server: ${data.error}`,
      ]);
    }
  } catch (err) {
    setStep("rpc", "rpc-server", "error");
    bump("fail");
    writeLog([`Client: calling ${method}()`, `Error: ${err.message}`]);
  }
});