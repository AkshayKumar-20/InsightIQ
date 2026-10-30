
import { useEffect, useRef, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, Copy, Database, Menu, Paperclip, Pencil, Plus, RefreshCw, RotateCcw, Send, Settings as SettingsIcon, Sparkles, Trash2, X } from "lucide-react";
import { api } from "./services/api";
import Chart from "./components/Chart";

const defaultSuggestions = [
  "What is the total revenue?",
  "Which product generated the highest revenue?",
  "Show monthly revenue trends.",
  "Which region generated the highest sales?",
  "Compare January and February revenue.",
];
const money = (value) => value == null ? "—" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
const number = (value) => value == null ? "—" : new Intl.NumberFormat("en-IN").format(Number(value));
const metricValue = (key, value) => {
  if (value == null || value === "") return "—";
  if (typeof value === "number" && Number.isFinite(value)) {
    return key.toLowerCase().includes("revenue") || key.toLowerCase().includes("value") ? money(value) : number(value);
  }
  return String(value);
};

function Logo() {
  return <div className="logo"><span>IQ</span><div><b>InsightIQ</b><small>Your business. Your data. Your answers.</small></div></div>;
}
function Status({ ok, children }) {
  return <span className={`status ${ok ? "ok" : "neutral"}`}><i />{children}</span>;
}
function Table({ rows }) {
  if (!rows?.length) return null;
  const keys = Object.keys(rows[0]);
  return <div className="table-scroll"><table><thead><tr>{keys.map((key) => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{keys.map((key) => <td key={key}>{typeof row[key] === "number" && key.includes("revenue") ? money(row[key]) : row[key] ?? "—"}</td>)}</tr>)}</tbody></table></div>;
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", role: "", password: "" });
  const [error, setError] = useState("");
  const [failedQuestion, setFailedQuestion] = useState("");
  const [notice, setNotice] = useState("");
  const submit = async (event) => {
    event.preventDefault(); setError("");
    try {
      if (mode === "register") {
        await api.register(form);
        setMode("login"); setForm({ name: "", email: form.email, role: "", password: "" });
        setNotice("Registration complete. Please sign in to continue.");
        return;
      }
      const result = await api.login(form);
      onAuthenticated(result.user);
    } catch (e) { setError(e.message); }
  };
  return <div className="auth-page"><div className="auth-card"><Logo /><h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1><p>{mode === "login" ? "Sign in to ask questions about your data." : "Create an account to keep your InsightIQ workspace."}</p><form onSubmit={submit}>{mode === "register" && <><input placeholder="Your name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /><input placeholder="Employee role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} required /></>}<input type="email" placeholder="Email address" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /><input type="password" placeholder="Password (6+ characters)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength="6" required />{notice && <div className="auth-notice">{notice}</div>}{error && <div className="auth-error">{error}</div>}<button className="auth-submit">{mode === "login" ? "Sign in" : "Register"}</button></form><button className="auth-switch" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setNotice(""); }}>{mode === "login" ? "New to InsightIQ? Create an account" : "Already have an account? Sign in"}</button></div></div>;
}

export default function App() {
  const [authUser, setAuthUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [failedQuestion, setFailedQuestion] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dataset, setDataset] = useState("Sales data");
  const [datasetProfile, setDatasetProfile] = useState(null);
  const [suggestions, setSuggestions] = useState(defaultSuggestions);
  const [profile, setProfile] = useState({ name: "User", email: "", role: "Analyst" });
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [preferences, setPreferences] = useState(() => {
    try {
      return { appearance: "light", enterToSend: true, showTimestamps: false, interpretationMode: "data analysis", responseDetail: "balanced", ...JSON.parse(localStorage.getItem("insightiq_preferences") || "{}") };
    } catch {
      return { appearance: "light", enterToSend: true, showTimestamps: false, interpretationMode: "data analysis", responseDetail: "balanced" };
    }
  });
  const threadRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    api.me().then((user) => { setAuthUser(user); setProfile(user); }).catch(() => setAuthUser(null)).finally(() => setAuthChecking(false));
  }, []);
  useEffect(() => { if (authUser) setProfile(authUser); }, [authUser]);

  const refresh = async (startNewChat = false) => {
    setRefreshing(true); setError("");
    try {
      const [health, cs, metadata] = await Promise.all([api.health(), api.conversations(), api.metadata()]);
      setConnected(health.status === "ok"); setConversations(cs.data || []);
      if (metadata.active_dataset?.startsWith("generic:")) {
        const activeProfile = metadata.generic_dataset;
        setDataset(activeProfile?.filename || "Uploaded CSV");
      } else if (metadata.active_dataset === "sales") {
        setDataset("Sales data");
      } else setDatasetProfile(null);
      const columns = metadata.generic_dataset?.columns || [];
      if (metadata.active_dataset?.startsWith("generic:") && columns.length) {
        const names = columns.map((column) => column.label.toLowerCase());
        const numeric = columns.find((column) => column.type === "number");
        const group = columns.find((column) => ["categorical", "text"].includes(column.type));
        setSuggestions([
          `How many records are in this file?`,
          numeric ? `What is the average ${numeric.label}?` : "Give me an overview of this file.",
          group ? `Which ${group.label} appears most often?` : "Which columns contain missing values?",
          numeric ? `What is the highest ${numeric.label}?` : "Show the first five rows.",
          names.some((name) => name.includes("date")) ? "Show records from 2025." : "Show the first five rows.",
        ]);
      } else setSuggestions(defaultSuggestions);
      if (startNewChat) { setConversationId(null); setMessages([]); setDatasetProfile(null); }
    } catch (e) { setConnected(false); setError(e.message); } finally { setRefreshing(false); }
  };
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    localStorage.setItem("insightiq_preferences", JSON.stringify(preferences));
    document.documentElement.dataset.theme = preferences.appearance;
  }, [preferences]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, loading]);
  if (authChecking) return <div className="auth-loading">Loading InsightIQ…</div>;
  if (!authUser) return <AuthScreen onAuthenticated={setAuthUser} />;
  const createConversation = async () => {
    const item = await api.createConversation();
    setConversations((old) => [item, ...old]); setConversationId(item.id); setMessages([]); setMobileOpen(false);
  };
  const selectConversation = async (id) => {
    const item = await api.conversation(id);
    setConversationId(id); setMessages(item.messages || []); setMobileOpen(false);
  };
  const renameConversation = async (item) => {
    const title = window.prompt("Rename conversation", item.title);
    if (!title?.trim() || title.trim() === item.title) return;
    try {
      const renamed = await api.renameConversation(item.id, title.trim());
      setConversations((old) => old.map((conversation) => conversation.id === item.id ? { ...conversation, title: renamed.title } : conversation));
    } catch (e) { setError(e.message); }
  };
  const retryFailedQuestion = () => {
    if (!failedQuestion) return;
    setMessages((old) => {
      const last = old.at(-1);
      const previous = old.at(-2);
      return last?.error && previous?.role === "user" && previous.content === failedQuestion ? old.slice(0, -2) : old;
    });
    ask(failedQuestion);
  };
  const ask = async (value = question) => {
    const text = value.trim(); if (!text || loading) return;
    setQuestion(""); setError(""); setFailedQuestion(""); setLoading(true);
    let id = conversationId;
    try {
      if (!id) { const created = await api.createConversation({ title: text.slice(0, 60) }); id = created.id; setConversationId(id); setConversations((old) => [created, ...old]); }
      const user = { role: "user", content: text, created_at: new Date().toISOString(), id: `u-${Date.now()}` };
      setMessages((old) => [...old, user]);
      let persistenceError = "";
      try {
        await api.addMessage(id, user);
      } catch (e) {
        persistenceError = `Question sent, but conversation history could not be saved: ${e.message}`;
      }
      const result = await api.chat(text, id);
      const assistant = { role: "assistant", content: result.answer, result, question: text, created_at: new Date().toISOString(), id: `a-${Date.now()}` };
      setMessages((old) => [...old, assistant]);
      try {
        await api.addMessage(id, assistant);
      } catch (e) {
        persistenceError = persistenceError
          ? `${persistenceError} Answer history could not be saved: ${e.message}`
          : `Answer returned, but conversation history could not be saved: ${e.message}`;
      }
      if (persistenceError) setError(persistenceError);
    } catch (e) {
      setFailedQuestion(text);
      setError("");
      setMessages((old) => [...old, {
        role: "assistant",
        content: e.message || "The question could not be answered.",
        error: true,
        created_at: new Date().toISOString(),
        id: `error-${Date.now()}`,
      }]);
    } finally { setLoading(false); }
  };
  const removeConversation = async (id) => { await api.deleteConversation(id); setConversations((old) => old.filter((item) => item.id !== id)); if (id === conversationId) { setConversationId(null); setMessages([]); setDatasetProfile(null); } };
  const upload = async (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    setUploading(true); setError("");
    try {
      let activeConversation = conversationId;
      if (!activeConversation) {
        const created = await api.createConversation({ title: file.name });
        activeConversation = created.id;
        setConversationId(activeConversation);
        setConversations((old) => [created, ...old]);
      }
      const result = await api.upload(file, activeConversation);
      setDataset(result.profile?.filename || result.filename || file.name);
      setDatasetProfile(result.profile || result.ingestion || null);
      setError("");
      setMessages((old) => [...old, { role: "assistant", content: `${file.name} is ready. Ask me about its columns, dates, employees, names, or numeric values.`, created_at: new Date().toISOString(), id: `upload-${Date.now()}` }]);
      await refresh();
    } catch (e) { setError(e.message); } finally { setUploading(false); event.target.value = ""; }
  };
  const saveProfile = async (event) => { event.preventDefault(); try { const updated = await api.updateProfile(profile); setProfile(updated); setAuthUser((current) => ({ ...current, ...updated })); setProfileOpen(false); } catch (e) { setError(e.message); } };
  const updatePreference = (key, value) => setPreferences((current) => ({ ...current, [key]: value }));
  const resetPreferences = () => setPreferences({ appearance: "light", enterToSend: true, showTimestamps: false, interpretationMode: "data analysis", responseDetail: "balanced" });
  const activeTitle = "Ask Your Data";

  return <div className="app">
    <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="sidebar-head"><Logo /><button className="icon-btn collapse" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight /> : <ChevronLeft />}</button></div>
      <button className="new-chat" onClick={createConversation}><Plus size={17} />{!collapsed && "New Chat"}</button>
      {!collapsed && <div className="recent"><span>Recent conversations</span>{conversations.slice(0, 8).map((item) => <div className="recent-row" key={item.id}><button onClick={() => selectConversation(item.id)}>{item.title}</button><button className="rename-btn" onClick={() => renameConversation(item)} aria-label="Rename conversation"><Pencil size={13} /></button><button className="delete-btn" onClick={() => removeConversation(item.id)} aria-label="Delete conversation"><Trash2 size={13} /></button></div>)}</div>}
      <div className="sidebar-bottom"><small><i className={connected ? "dot online" : "dot"} />{!collapsed && (connected ? "Database connected" : "Database unavailable")}</small></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="mobile-menu icon-btn" onClick={() => setMobileOpen(!mobileOpen)}><Menu /></button><div><b>InsightIQ</b><span>Ask questions about your uploaded data</span></div><div className="top-actions"><Status ok={connected}>{connected ? "Connected" : "Offline"}</Status><button className="icon-btn refresh-btn" onClick={() => refresh(true)} disabled={refreshing} aria-label="Start a new chat"><RefreshCw size={17} className={refreshing ? "spin" : ""} /></button><div className="settings-wrap"><button className="settings-button" onClick={() => setSettingsOpen((open) => !open)} aria-expanded={settingsOpen}><SettingsIcon size={14} /> Settings</button>{settingsOpen && <div className="settings-popover" role="dialog" aria-label="InsightIQ settings"><div className="settings-header"><strong>Settings</strong><button className="settings-close" onClick={() => setSettingsOpen(false)}><X size={14} /></button></div><div className="settings-section"><span>Appearance</span><div className="settings-options"><button className={preferences.appearance === "light" ? "selected" : ""} onClick={() => updatePreference("appearance", "light")}>Light</button><button className={preferences.appearance === "dark" ? "selected" : ""} onClick={() => updatePreference("appearance", "dark")}>Dark</button></div></div><div className="settings-section"><span>Chat preferences</span><label className="settings-toggle"><span>Enter to send</span><input type="checkbox" checked={preferences.enterToSend} onChange={(event) => updatePreference("enterToSend", event.target.checked)} /></label><label className="settings-toggle"><span>Show timestamps</span><input type="checkbox" checked={preferences.showTimestamps} onChange={(event) => updatePreference("showTimestamps", event.target.checked)} /></label></div><div className="settings-section"><span>AI preferences</span><label className="settings-select"><span>Interpretation mode</span><select value={preferences.interpretationMode} onChange={(event) => updatePreference("interpretationMode", event.target.value)}><option value="data analysis">Data analysis</option><option value="conversation">Conversation</option></select></label><label className="settings-select"><span>Response detail</span><select value={preferences.responseDetail} onChange={(event) => updatePreference("responseDetail", event.target.value)}><option value="compact">Compact</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></label></div><div className="settings-section"><span>Data settings</span><div className="settings-data"><strong>{datasetProfile?.filename || dataset}</strong><small>{datasetProfile ? `${datasetProfile.row_count ?? 0} rows · ${datasetProfile.column_count ?? 0} columns` : "No CSV uploaded"}</small></div></div><button className="reset-settings" onClick={resetPreferences}>Reset to defaults</button></div>}</div><button className="profile-button" onClick={() => setProfileOpen(true)}><div className="avatar">{(authUser.name || "U").slice(0, 1).toUpperCase()}</div><span>{authUser.name}</span></button><button className="sign-out" onClick={async () => { try { await api.logout(); } finally { setAuthUser(null); } }}>Sign out</button></div></header>
      {error && <div className="error"><X size={16} /><span>{error}</span></div>}
      <div className="workspace">
        <section id="ask" className={`chat ${messages.length ? "has-messages" : ""}`}>
          {!messages.length ? <div className="welcome"><div className="welcome-icon"><Sparkles size={24} /></div><h1>Your business, understood.</h1><p>{datasetProfile ? <>Ask anything about <b>{dataset}</b>.</> : "Upload a CSV to start asking questions about your data."}</p><div className="suggestions">{suggestions.map((item) => <button key={item} onClick={() => ask(item)}>{item}<ChevronRight size={15} /></button>)}</div></div> : <div className="thread">{messages.map((message) => <article className={`message ${message.role} ${message.error ? "message-error" : ""}`} key={message.id}><div className="message-mark">{message.role === "user" ? "A" : <Sparkles size={16} />}</div><div className="message-body"><div className="message-heading"><span className="message-label">{message.role === "user" ? "You" : "InsightIQ"}</span>{preferences.showTimestamps && message.created_at && <time>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>}</div><p>{message.content}</p>{message.error ? <div className="error-response"><AlertCircle size={16} /><span>{message.content}</span><button className="retry-btn" onClick={retryFailedQuestion}><RotateCcw size={13} /> Retry</button></div> : message.role === "assistant" && <button className="copy message-copy" onClick={() => navigator.clipboard?.writeText(message.content)}><Copy size={14} /> Copy</button>}{message.result && <div className="result"><div className="result-meta"><Status ok={false}>Grounded in {message.result.dataset_name || dataset}</Status></div>{Object.keys(message.result.metrics || {}).length > 0 && <div className="metrics">{Object.entries(message.result.metrics).filter(([k]) => typeof message.result.metrics[k] !== "object").map(([key, value]) => <div key={key}><small>{key.replaceAll("_", " ")}</small><b>{metricValue(key, value)}</b></div>)}</div>}{message.result.chart && <Chart data={message.result.chart.data} type={message.result.chart.type} x={message.result.chart.x_key} y={message.result.chart.y_key} />}{message.result.table?.length > 0 && <Table rows={message.result.table} />}{preferences.responseDetail !== "compact" && <details><summary>How this was calculated</summary><p>{message.result.sql_explanation}</p></details>}</div>}</div></article>)}{loading && <div className="message assistant"><div className="message-mark"><Sparkles size={16} /></div><div className="typing"><i /><i /><i /></div></div>}</div>}<div ref={messagesEndRef} />
          {datasetProfile?.filename && datasetProfile.row_count != null && datasetProfile.column_count != null && <aside className="dataset-panel"><div><Database size={16} /><strong>{dataset}</strong><button className="dataset-remove" onClick={() => setDatasetProfile(null)} aria-label="Remove uploaded dataset"><X size={14} /></button></div><span>{datasetProfile.row_count} rows · {datasetProfile.column_count} columns</span><span>{datasetProfile.missing_values ?? 0} missing values · {datasetProfile.duplicate_rows ?? 0} duplicate rows</span></aside>}
          <div className="composer"><label className="attach-btn" title="Upload CSV"><Paperclip size={18} /><input type="file" accept=".csv,text/csv" onChange={upload} disabled={uploading} /></label><textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && preferences.enterToSend) { e.preventDefault(); ask(); } }} placeholder={uploading ? "Uploading CSV..." : "Ask InsightIQ about your uploaded data..."} rows="1" /><button onClick={() => ask()} disabled={loading || !question.trim()} aria-label="Send"><Send size={18} /></button><small>+ upload CSV · Active file: {dataset}{datasetProfile ? ` · ${datasetProfile.row_count ?? 0} rows · ${datasetProfile.column_count ?? 0} columns${datasetProfile.missing_values ? ` · ${datasetProfile.missing_values} missing` : ""}` : ""} · {preferences.enterToSend ? "Enter to send · " : ""}Shift + Enter for a new line</small></div>
        </section>
      </div>
      {profileOpen && <div className="modal-backdrop" onClick={() => setProfileOpen(false)}><form className="profile-modal" onSubmit={saveProfile} onClick={(event) => event.stopPropagation()}><div className="modal-head"><h2>Profile settings</h2><button type="button" className="icon-btn" onClick={() => setProfileOpen(false)}><X size={16} /></button></div><label>Name<input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} /></label><label>Email<input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} /></label><label>Role<input value={profile.role} onChange={(e) => setProfile({ ...profile, role: e.target.value })} /></label><button className="save-profile">Save profile</button></form></div>}
    </main>
  </div>;
}
