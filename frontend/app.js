const users = {
  alice: "secret123",
  bob: "pass456",
  admin: "admin789",
};

const stats = {
  calls: 0,
  ok: 0,
  fail: 0,
};

const form = document.querySelector("#rpc-form");
const sendButton = document.querySelector("#send");
const logBox = document.querySelector("#log");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function setStep(name, state = "active") {
  document.querySelectorAll(".step").forEach((step) => {
    step.classList.remove("active", "error");
    if (step.dataset.step === name) step.classList.add(state);
  });
}

function bump(key) {
  stats[key] += 1;
  document.querySelector(`#${key}`).textContent = stats[key];
}

function tokenFor(username, method, mode) {
  const payload = {
    sub: username,
    method,
    mode,
    exp: Date.now() + 60 * 60 * 1000,
  };

  return btoa(JSON.stringify(payload));
}

function responseFor(method, username) {
  const id = Math.floor(1000 + Math.random() * 9000);

  const responses = {
    getData: { status: "ok", user: username, records: ["record_alpha", "record_beta"] },
    writeRecord: { status: "written", id, data: "hello_world" },
    deleteItem: { status: "deleted", item_id: 1, affected: 1 },
    ping: { pong: true, user: username, latency: `${Math.floor(2 + Math.random() * 12)}ms` },
  };

  return responses[method];
}

function writeLog(lines) {
  logBox.textContent = lines.join("\n");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  sendButton.disabled = true;

  const data = new FormData(form);
  const username = data.get("username").trim();
  const password = data.get("password").trim();
  const mode = data.get("mode");
  const method = data.get("method");
  const modeLabel = mode === "symmetric" ? "AES symmetric" : "RSA asymmetric";

  bump("calls");
  setStep("client");
  writeLog([
    `Client: preparing ${method} with ${modeLabel}`,
    "Client: credentials encrypted",
  ]);
  await sleep(450);

  setStep("auth");
  writeLog([
    `Client: preparing ${method} with ${modeLabel}`,
    "Client: credentials encrypted",
    "Auth Service: validating credentials",
  ]);
  await sleep(450);

  if (users[username] !== password) {
    bump("fail");
    setStep("auth", "error");
    writeLog([
      `Client: preparing ${method} with ${modeLabel}`,
      "Client: credentials encrypted",
      `Auth Service: rejected ${username || "unknown user"}`,
    ]);
    sendButton.disabled = false;
    return;
  }

  const token = tokenFor(username, method, mode);
  setStep("server");
  writeLog([
    `Client: preparing ${method} with ${modeLabel}`,
    "Client: credentials encrypted",
    `Auth Service: token issued for ${username}`,
    "RPC Server: verifying token",
  ]);
  await sleep(450);

  bump("ok");
  const result = responseFor(method, username);
  writeLog([
    `Client: preparing ${method} with ${modeLabel}`,
    "Client: credentials encrypted",
    `Auth Service: token issued for ${username}`,
    `Token: ${token.slice(0, 42)}...`,
    `RPC Server: ${method} complete`,
    "",
    JSON.stringify(result, null, 2),
  ]);

  sendButton.disabled = false;
});
