const base = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path) {
  const response = await fetch(base + path, { credentials: "include" });
  if (!response.ok) throw new Error(await response.text() || "Request failed");
  return response.json();
}

export const api = {
  login: async (payload) => request("/api/auth/login", "POST", payload),
  register: async (payload) => request("/api/auth/register", "POST", payload),
  me: () => get("/api/auth/me"),
  logout: async () => {
    const response = await fetch(base + "/api/auth/logout", { method: "POST", credentials: "include" });
    if (!response.ok) throw new Error("Could not sign out.");
    return response.json();
  },
  health: () => get("/api/health"),
  metadata: () => get("/api/metadata"),
  summary: () => get("/api/analytics/summary"),
  trends: () => get("/api/analytics/trends"),
  monthly: () => get("/api/analytics/monthly"),
  products: () => get("/api/analytics/products"),
  regions: () => get("/api/analytics/regions"),
  quality: () => get("/api/data-quality"),
  profile: () => get("/api/profile"),
  conversations: () => get("/api/conversations"),
  conversation: (id) => get(`/api/conversations/${id}`),
  createConversation: async (payload = {}) => {
    const response = await fetch(base + "/api/conversations", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error("Could not create conversation.");
    return response.json();
  },
  deleteConversation: async (id) => {
    const response = await fetch(base + `/api/conversations/${id}`, { method: "DELETE", credentials: "include" });
    if (!response.ok) throw new Error("Could not delete conversation.");
    return response.json();
  },
  renameConversation: async (id, title) => {
    const response = await fetch(base + `/api/conversations/${id}`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not rename conversation.");
    return data;
  },
  updateProfile: async (profile) => {
    const response = await fetch(base + "/api/profile", { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not update profile.");
    return data;
  },
  addMessage: async (id, message) => {
    const response = await fetch(base + `/api/conversations/${id}/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(message) });
    if (!response.ok) throw new Error("Could not save conversation.");
    return response.json();
  },
  upload: async (file, conversationId) => {
    const body = new FormData();
    body.append("file", file);
    const query = conversationId ? `?conversation_id=${conversationId}` : "";
    const response = await fetch(base + "/api/upload" + query, { method: "POST", credentials: "include", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "CSV upload failed.");
    return data;
  },
  ask: async (question) => {
    const response = await fetch(base + "/api/ask", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The question could not be answered.");
    return data;
  },
  chat: async (question, conversationId) => {
    const response = await fetch(base + "/api/chat", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, conversation_id: conversationId }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The question could not be answered.");
    if (!data.success || typeof data.answer !== "string" || !data.answer.trim()) {
      throw new Error("The assistant returned an empty answer.");
    }
    return data;
  },
};

async function request(path, method, body) {
  const response = await fetch(base + path, { method, credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed.");
  return data;
}
