import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bell,
  BookmarkCheck,
  BookmarkMinus,
  BookmarkPlus,
  CalendarClock,
  CheckCircle2,
  FileText,
  LockKeyhole,
  LogOut,
  Mail,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Plus,
  Upload,
  User,
  X,
} from "lucide-react";
import { createClient } from "@supabase/supabase-js";
import { AnimatePresence, motion } from "framer-motion";
import { api, API_URL, SUPABASE_ANON_KEY, SUPABASE_URL } from "./api";
import { FloatingCompassHelp, OnboardingGuide } from "./features/onboarding/UserGuide";
import { SearchHistoryPanel } from "./features/search/SearchHistoryPanel";
import type {
  AdminHealth,
  EvalRunRecord,
  ApplicationTaskRecord,
  GeneratedDocumentRecord,
  LoadingKey,
  Notice,
  OpportunityRecord,
  SearchJob,
  SearchResultPayload,
  StudentProfile,
  Tab,
  UploadedFileRecord,
} from "./types";
import "./style.css";

const supabase = SUPABASE_URL && SUPABASE_ANON_KEY ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const EMPTY_PROFILE: StudentProfile = {
  full_name: null,
  country: null,
  degree: null,
  field: null,
  semester: null,
  cgpa: null,
  skills: [],
  preferred_countries: [],
  preferred_regions: [],
  preferred_opportunity_types: [],
  budget_preference: null,
  ielts_status: null,
  gre_status: null,
  career_goal: null,
};

const ONBOARDING_KEY = "compass_redirect_account";

const navItems: Array<{ target: Exclude<Tab, "opportunityDetail">; label: string; icon: React.ReactNode }> = [
  { target: "account", label: "Account", icon: <User size={17} /> },
  { target: "search", label: "Search", icon: <Search size={17} /> },
  { target: "opportunities", label: "Opportunities", icon: <BookmarkPlus size={17} /> },
  { target: "tracker", label: "Tracker", icon: <Settings size={17} /> },
  { target: "documents", label: "Documents", icon: <FileText size={17} /> },
  { target: "uploads", label: "Uploads", icon: <Upload size={17} /> },
  { target: "notifications", label: "Notifications", icon: <Bell size={17} /> },
  { target: "admin", label: "Review", icon: <ShieldAlert size={17} /> },
];

function useDebouncedValue<T>(value: T, delay = 420): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timeout);
  }, [value, delay]);

  return debounced;
}

function splitListInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function mergeListItems(existing: string[], incoming: string[]): string[] {
  const seen = new Set(existing.map((item) => item.toLowerCase()));
  const merged = [...existing];
  for (const item of incoming) {
    const key = item.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(item);
    }
  }
  return merged;
}

function rowToProfile(row: Record<string, unknown> | null | undefined): StudentProfile {
  if (!row) return { ...EMPTY_PROFILE };
  return {
    full_name: (row.full_name as string | null) ?? null,
    country: (row.country as string | null) ?? null,
    degree: (row.degree as string | null) ?? null,
    field: (row.field as string | null) ?? null,
    semester: (row.semester as string | null) ?? null,
    cgpa: typeof row.cgpa === "number" ? row.cgpa : row.cgpa ? Number(row.cgpa) : null,
    skills: Array.isArray(row.skills) ? row.skills.map(String) : splitListInput(String(row.skills ?? "")),
    preferred_countries: Array.isArray(row.preferred_countries)
      ? row.preferred_countries.map(String)
      : splitListInput(String(row.preferred_countries ?? "")),
    preferred_regions: Array.isArray(row.preferred_regions)
      ? row.preferred_regions.map(String)
      : splitListInput(String(row.preferred_regions ?? "")),
    preferred_opportunity_types: Array.isArray(row.preferred_opportunity_types)
      ? row.preferred_opportunity_types.map(String)
      : splitListInput(String(row.preferred_opportunity_types ?? "")),
    budget_preference: (row.budget_preference as string | null) ?? null,
    ielts_status: (row.ielts_status as string | null) ?? null,
    gre_status: (row.gre_status as string | null) ?? null,
    career_goal: (row.career_goal as string | null) ?? null,
  };
}

function isProfileComplete(profile: StudentProfile | null): boolean {
  if (!profile) return false;
  return Boolean(profile.country?.trim() && profile.degree?.trim() && profile.field?.trim());
}

function profileSummary(profile: StudentProfile | null): string {
  if (!profile || !isProfileComplete(profile)) return "Add your academic background and goals to improve matching.";
  const parts = [
    profile.degree,
    profile.field,
    profile.country ? `from ${profile.country}` : null,
    profile.career_goal,
  ].filter(Boolean);
  return parts.join(" · ");
}
function formatDisplayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not listed";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Not listed";
  const text = String(value).trim();
  if (!text || text.toLowerCase() === "null") return "Not listed";
  if (text.startsWith("[") && text.endsWith("]")) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) return parsed.join(", ");
    } catch {
      return text;
    }
  }
  return text;
}

function formatDeadline(value: string | null | undefined): string {
  if (!value) return "Not listed";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function emailStatusLabel(task: ApplicationTaskRecord): string {
  const status = task.email_status;
  if (status?.sent) {
    const sentDate = status.sent_at ? formatDeadline(status.sent_at) : null;
    return sentDate ? `Email sent ${sentDate}` : "Email sent";
  }
  return "Email not sent yet";
}

function reminderDayLabel(day: number): string {
  return day === 0 ? "Due day" : `${day} ${day === 1 ? "day" : "days"} before deadline`;
}

function uploadPurposeLabel(upload: UploadedFileRecord): string {
  const purpose = String(upload.purpose ?? "document").replace(/_/g, " ");
  return purpose.charAt(0).toUpperCase() + purpose.slice(1);
}

function bestDocumentUpload(rows: UploadedFileRecord[]): UploadedFileRecord | undefined {
  const scored = rows
    .filter((row) => row.extracted_text)
    .map((row) => {
      const purpose = String(row.purpose ?? "").toLowerCase();
      const path = String(row.path ?? "").toLowerCase();
      const score =
        (purpose.includes("cv") || path.includes("cv") || path.includes("resume") ? 3 : 0) +
        (purpose.includes("transcript") || path.includes("transcript") ? 2 : 0);
      return { row, score };
    });
  scored.sort((a, b) => b.score - a.score);
  return scored[0]?.row;
}

function documentRootId(document: GeneratedDocumentRecord): string {
  return document.parent_document_id || document.id;
}

function groupDocumentVersions(documents: GeneratedDocumentRecord[]): Array<{ rootId: string; versions: GeneratedDocumentRecord[] }> {
  const groups = new Map<string, GeneratedDocumentRecord[]>();
  for (const document of documents) {
    const rootId = documentRootId(document);
    groups.set(rootId, [...(groups.get(rootId) ?? []), document]);
  }
  return Array.from(groups.entries())
    .map(([rootId, versions]) => ({
      rootId,
      versions: versions.sort((a, b) => (b.version_number ?? 1) - (a.version_number ?? 1)),
    }))
    .sort((a, b) => {
      const aTime = new Date(a.versions[0]?.updated_at ?? a.versions[0]?.created_at ?? 0).getTime();
      const bTime = new Date(b.versions[0]?.updated_at ?? b.versions[0]?.created_at ?? 0).getTime();
      return bTime - aTime;
    });
}

function trustLabel(level?: string): string {
  if (!level) return "Unknown";
  return level.replace(/_/g, " ");
}

const pageMeta: Record<Tab, { title: string; eyebrow: string }> = {
  account: { title: "Your Account", eyebrow: "Student profile for matching" },
  search: { title: "Opportunity Search", eyebrow: "Profile-aware discovery" },
  opportunityDetail: { title: "Opportunity Detail", eyebrow: "Eligibility, source, and next actions" },
  opportunities: { title: "Opportunities", eyebrow: "Saved and discovered listings" },
  tracker: { title: "Application Tracker", eyebrow: "Progress and next actions" },
  documents: { title: "Documents", eyebrow: "Grounded drafts" },
  uploads: { title: "Uploads", eyebrow: "Posters, PDFs, CVs" },
  notifications: { title: "Notifications", eyebrow: "Reminder preferences" },
  admin: { title: "Review Console", eyebrow: "Quality and trust signals" },
};

type ConfirmationRequest = {
  title: string;
  detail: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => Promise<void> | void;
};

function App() {
  const [token, setToken] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [compassUserId, setCompassUserId] = useState("");
  const [tab, setTab] = useState<Tab>("search");
  const [output, setOutput] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);
  const [profileForm, setProfileForm] = useState<StudentProfile>({ ...EMPTY_PROFILE });
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [isNewAccount, setIsNewAccount] = useState(false);
  const [loading, setLoading] = useState<Partial<Record<LoadingKey, boolean>>>({});
  const [busyMessage, setBusyMessage] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationRequest | null>(null);
  const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
  const [discoveredOpportunities, setDiscoveredOpportunities] = useState<OpportunityRecord[]>([]);
  const [searchSummary, setSearchSummary] = useState<SearchResultPayload | null>(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState<OpportunityRecord | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [workspaceOpportunities, setWorkspaceOpportunities] = useState<OpportunityRecord[]>([]);
  const [workspaceSearchJobs, setWorkspaceSearchJobs] = useState<SearchJob[]>([]);
  const [workspaceDocuments, setWorkspaceDocuments] = useState<GeneratedDocumentRecord[]>([]);
  const [workspaceUploads, setWorkspaceUploads] = useState<UploadedFileRecord[]>([]);
  const [workspaceTasks, setWorkspaceTasks] = useState<ApplicationTaskRecord[]>([]);
  const atlasTabs: Tab[] = ["search", "opportunities", "tracker", "documents", "uploads", "notifications"];
  const isAtlasTab = atlasTabs.includes(tab);
  const effectiveProfile = profile ?? profileForm;
  const profileComplete = isProfileComplete(effectiveProfile);
  const hasUploads = workspaceUploads.length > 0;
  const hasOpportunities = workspaceOpportunities.length > 0 || discoveredOpportunities.length > 0;
  const opportunityOptions = useMemo(
    () => mergeOpportunityLists(workspaceOpportunities, discoveredOpportunities),
    [workspaceOpportunities, discoveredOpportunities],
  );
  const visibleNavItems = useMemo(
    () => navItems.filter((item) => item.target !== "admin" || isAdmin),
    [isAdmin],
  );

  const notify = (kind: "success" | "error", message: string) => {
    setNotice({ kind, message });
  };

  const runAction = async (key: LoadingKey, message: string, action: () => Promise<void>, successMessage?: string) => {
    setLoading((current) => ({ ...current, [key]: true }));
    setBusyMessage(message);
    try {
      await action();
      if (successMessage) notify("success", successMessage);
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setLoading((current) => ({ ...current, [key]: false }));
      setBusyMessage("");
    }
  };

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? "");
      setUserEmail(data.session?.user.email ?? "");
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setToken(session?.access_token ?? "");
      setUserEmail(session?.user.email ?? "");
    });
    return () => subscription.subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase?.auth.signOut();
    setToken("");
    setUserEmail("");
    setIsAdmin(false);
    setCompassUserId("");
    setOutput(null);
    setDiscoveredOpportunities([]);
    setSearchSummary(null);
    setWorkspaceOpportunities([]);
    setWorkspaceSearchJobs([]);
    setWorkspaceDocuments([]);
    setWorkspaceUploads([]);
    setWorkspaceTasks([]);
    notify("success", "Signed out successfully.");
  };

  const loadProfile = async () => {
    const result = await api("/profile/me", token);
    const loaded = rowToProfile(result.profile);
    setProfile(loaded);
    setProfileForm(loaded);
    setProfileLoaded(true);
    setCompassUserId(result.compass_user_id ?? result.profile?.compass_user_id ?? "");
    setIsAdmin(Boolean(result.is_admin));
    return loaded;
  };

  const saveProfile = async () =>
    runAction("profile", "Saving your profile...", async () => {
      const payload: StudentProfile = {
        ...profileForm,
        cgpa: profileForm.cgpa === null || Number.isNaN(profileForm.cgpa) ? null : profileForm.cgpa,
      };
      const result = await api("/profile/me", token, { method: "PUT", body: JSON.stringify(payload) });
      const saved = rowToProfile(result.profile ?? result.saved_profile);
      setProfile(saved);
      setProfileForm(saved);
      setProfileLoaded(true);
      setIsNewAccount(false);
      setCompassUserId(result.compass_user_id ?? result.saved_profile?.compass_user_id ?? "");
      setIsAdmin(Boolean(result.is_admin));
      setOutput(result);
    }, "Profile saved successfully.");

  const loadWorkspaceData = async () => {
    if (!token) return;
    setLoading((current) => ({ ...current, workspace: true }));
    try {
      const [opportunityResult, jobResult, documentResult, uploadResult, trackerResult] = await Promise.all([
        api<{ opportunities?: OpportunityRecord[] }>("/opportunities", token),
        api<{ jobs?: SearchJob[] }>("/opportunities/search/jobs", token),
        api<{ documents?: GeneratedDocumentRecord[] }>("/documents", token),
        api<{ uploads?: UploadedFileRecord[] }>("/uploads", token),
        api<{ tracker?: ApplicationTaskRecord[] }>("/tracker", token),
      ]);
      setWorkspaceOpportunities(opportunityResult.opportunities ?? []);
      setWorkspaceSearchJobs(jobResult.jobs ?? []);
      setWorkspaceDocuments(documentResult.documents ?? []);
      setWorkspaceUploads(uploadResult.uploads ?? []);
      setWorkspaceTasks(trackerResult.tracker ?? []);
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Could not load workspace data.");
    } finally {
      setLoading((current) => ({ ...current, workspace: false }));
    }
  };

  useEffect(() => {
    if (!token) {
      setProfile(null);
      setProfileForm({ ...EMPTY_PROFILE });
      setProfileLoaded(false);
      setIsNewAccount(false);
      setIsAdmin(false);
      setCompassUserId("");
      setWorkspaceOpportunities([]);
      setWorkspaceSearchJobs([]);
      setWorkspaceDocuments([]);
      setWorkspaceUploads([]);
      setWorkspaceTasks([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const loaded = await loadProfile();
        if (cancelled) return;
        const shouldOnboard = sessionStorage.getItem(ONBOARDING_KEY) === "1";
        if (shouldOnboard) {
          sessionStorage.removeItem(ONBOARDING_KEY);
          setIsNewAccount(true);
          setTab("account");
        } else if (!isProfileComplete(loaded)) {
          setTab("account");
        } else {
          setTab("search");
        }
        void loadWorkspaceData();
      } catch (error) {
        if (!cancelled) notify("error", error instanceof Error ? error.message : "Could not load profile.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!isAdmin && tab === "admin") {
      setTab("search");
    }
  }, [isAdmin, tab]);

  const runSearch = async () => {
    const settledQuery = query.trim();
    if (!settledQuery) return;
    setLoading((current) => ({ ...current, search: true }));
    setBusyMessage("Starting search job...");
    setDiscoveredOpportunities([]);
    setSearchSummary(null);
    try {
      const result = await api("/opportunities/search", token, {
        method: "POST",
        body: JSON.stringify({ query: settledQuery, profile: effectiveProfile, max_results_per_query: 2 }),
      });
      setSearchJob(result.job);
      setOutput(result);
      notify("success", "Search job started.");
    } catch (error) {
      setLoading((current) => ({ ...current, search: false }));
      setBusyMessage("");
      notify("error", error instanceof Error ? error.message : "Search failed to start.");
    }
  };

  const openOpportunityDetail = async (item: OpportunityRecord) => {
    setSelectedOpportunity(item);
    setTab("opportunityDetail");
    setOutput({ opportunity: item });
    if (!item.id) return;
    await runAction("opportunities", "Loading opportunity details...", async () => {
      const result = await api(`/opportunities/${item.id}`, token);
      const detail = { ...item, ...(result.opportunity ?? {}) };
      setSelectedOpportunity(detail);
      setOutput({ opportunity: detail });
    });
  };

  const cancelSearch = async () => {
    if (!searchJob) return;
    await cancelSearchHistoryJob(searchJob);
  };

  const retrySearch = async () => {
    if (!searchJob) return;
    await retrySearchHistoryJob(searchJob);
  };

  const cancelSearchHistoryJob = async (job: SearchJob) => {
    await runAction("search", "Cancelling search job...", async () => {
      const result = await api<{ job: SearchJob }>(`/opportunities/search/jobs/${job.id}/cancel`, token, { method: "POST", body: "{}" });
      setSearchJob(result.job);
      setOutput(result);
      setBusyMessage("");
      await loadWorkspaceData();
    }, "Search cancelled.");
  };

  const retrySearchHistoryJob = async (job: SearchJob) => {
    await runAction("search", "Retrying search job from saved progress...", async () => {
      const result = await api<{ job: SearchJob }>(`/opportunities/search/jobs/${job.id}/retry`, token, { method: "POST", body: "{}" });
      setSearchJob(result.job);
      setOutput(result);
      setBusyMessage(result.job.progress_message || "Queued for retry...");
      await loadWorkspaceData();
    }, "Search retry queued.");
  };

  const deleteSearchHistoryJob = async (job: SearchJob) => {
    const label = job.query || job.progress_message || "this search";
    if (!window.confirm(`Delete "${label}" from search history?`)) return;
    await runAction("search", "Deleting search history entry...", async () => {
      const result = await api(`/opportunities/search/jobs/${job.id}`, token, { method: "DELETE" });
      if (searchJob?.id === job.id) {
        setSearchJob(null);
        setSearchSummary(null);
        setDiscoveredOpportunities([]);
        setBusyMessage("");
      }
      setWorkspaceSearchJobs((current) => current.filter((item) => item.id !== job.id));
      setOutput(result);
    }, "Search history entry deleted.");
  };

  useEffect(() => {
    if (!token || !searchJob || !["queued", "running"].includes(searchJob.status)) return;
    const interval = window.setInterval(async () => {
      try {
        const result = await api(`/opportunities/search/jobs/${searchJob.id}`, token);
        const job = result.job as SearchJob;
        setSearchJob(job);
        setOutput(result);
        setBusyMessage(job.progress_message || "Search job is running...");
        if (job.status === "completed") {
          const payload = (job.result ?? null) as SearchResultPayload | null;
          setSearchSummary(payload);
          setDiscoveredOpportunities(payload?.opportunities ?? []);
          setOutput(payload ?? result);
          setLoading((current) => ({ ...current, search: false }));
          setBusyMessage("");
          if ((payload?.opportunities?.length ?? 0) > 0) {
            setTab("opportunities");
          }
          void loadWorkspaceData();
          notify("success", "Search completed successfully.");
        }
        if (job.status === "failed") {
          setLoading((current) => ({ ...current, search: false }));
          setBusyMessage("");
          notify("error", job.error || "Search job failed.");
        }
        if (job.status === "cancelled") {
          setLoading((current) => ({ ...current, search: false }));
          setBusyMessage("");
          notify("success", "Search cancelled.");
        }
      } catch (error) {
        setLoading((current) => ({ ...current, search: false }));
        setBusyMessage("");
        notify("error", error instanceof Error ? error.message : "Could not poll search job.");
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [token, searchJob?.id, searchJob?.status]);

  if (!token) {
    return <AuthScreen setOutput={setOutput} notify={notify} notice={notice} clearNotice={() => setNotice(null)} />;
  }

  return (
    <main className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <button className="sidebar-brand-toggle" onClick={() => setSidebarCollapsed((current) => !current)} aria-label="Toggle menu" title="Toggle sidebar">
          <SidebarBrandLockup collapsed={sidebarCollapsed} />
        </button>
        <nav className="sidebar-nav" aria-label="Primary">
          {visibleNavItems.map((item) => (
            <NavButton key={item.target} tab={tab} target={item.target} setTab={setTab} icon={item.icon} label={item.label} compact={sidebarCollapsed} />
          ))}
        </nav>
        <div className="account">
          <div className="account-meta">
            <span>{userEmail || "Signed in"}</span>
          </div>
          <button className="ghost-button" onClick={signOut}><LogOut size={16} /> Sign out</button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <span className="eyebrow">{pageMeta[tab].eyebrow}</span>
            <h2>{pageMeta[tab].title}</h2>
          </div>
        </header>

        {busyMessage && <BusyBanner message={busyMessage} />}

        <div className={`content-grid ${isAtlasTab ? "documents-content-grid atlas-content-grid" : ""}`.trim()}>
          <div className="primary-pane">
            {tab === "account" && (
              <OnboardingGuide
                profileComplete={profileComplete}
                hasUploads={hasUploads}
                hasOpportunities={hasOpportunities}
                isAdmin={isAdmin}
                setTab={setTab}
              />
            )}
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
              >
                {tab === "account" && (
                  <AccountPanel
                    profileForm={profileForm}
                    setProfileForm={setProfileForm}
                    saveProfile={saveProfile}
                    loadProfile={() => runAction("profile", "Loading profile...", async () => {
                      await loadProfile();
                    }, "Profile loaded.")}
                    profileLoaded={profileLoaded}
                    isNewAccount={isNewAccount}
                    profileComplete={profileComplete}
                    compassUserId={compassUserId}
                    setTab={setTab}
                    loading={loading}
                  />
                )}
                {tab === "search" && (
                  <SearchPanel
                    profile={effectiveProfile}
                    profileComplete={profileComplete}
                    hasUploads={hasUploads}
                    setTab={setTab}
                    query={query}
                    debouncedQuery={debouncedQuery}
                    setQuery={setQuery}
                    runSearch={runSearch}
                    searchJob={searchJob}
                    searchSummary={searchSummary}
                    discoveredOpportunities={discoveredOpportunities}
                    onViewDetails={openOpportunityDetail}
                    cancelSearch={cancelSearch}
                    retrySearch={retrySearch}
                    searchJobs={workspaceSearchJobs}
                    refreshSearchJobs={loadWorkspaceData}
                    onCancelSearchJob={cancelSearchHistoryJob}
                    onRetrySearchJob={retrySearchHistoryJob}
                    onDeleteSearchJob={deleteSearchHistoryJob}
                    loading={loading}
                  />
                )}
                {tab === "opportunityDetail" && (
                  <OpportunityDetailPanel
                    item={selectedOpportunity}
                    token={token}
                    setOutput={setOutput}
                    runAction={runAction}
                    setTab={setTab}
                    loading={loading}
                    refreshWorkspace={loadWorkspaceData}
                  />
                )}
                {tab === "opportunities" && (
                  <OpportunityPanel
                    token={token}
                    setOutput={setOutput}
                    runAction={runAction}
                    loading={loading}
                    discoveredOpportunities={discoveredOpportunities}
                    onViewDetails={openOpportunityDetail}
                    setTab={setTab}
                  />
                )}
                {tab === "tracker" && <TrackerPanel token={token} setOutput={setOutput} runAction={runAction} loading={loading} setTab={setTab} hasOpportunities={hasOpportunities} tasks={workspaceTasks} refreshWorkspace={loadWorkspaceData} opportunityOptions={opportunityOptions} requestConfirmation={setConfirmation} />}
                {tab === "documents" && <DocumentPanel token={token} profile={profile} setOutput={setOutput} runAction={runAction} loading={loading} opportunityOptions={opportunityOptions} />}
                {tab === "uploads" && <UploadPanel token={token} setOutput={setOutput} runAction={runAction} loading={loading} uploads={workspaceUploads} refreshWorkspace={loadWorkspaceData} />}
                {tab === "notifications" && <NotificationPanel token={token} setOutput={setOutput} runAction={runAction} loading={loading} tasks={workspaceTasks} />}
                {tab === "admin" && isAdmin && <AdminPanel token={token} setOutput={setOutput} runAction={runAction} loading={loading} />}
              </motion.div>
            </AnimatePresence>
          </div>
          {!isAtlasTab && (
            <InsightPanel
              tab={tab}
              profileComplete={profileComplete}
              searchJob={searchJob}
              searchSummary={searchSummary}
              savedOpportunities={workspaceOpportunities}
              documents={workspaceDocuments}
              uploads={workspaceUploads}
            />
          )}
        </div>
      </section>
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {visibleNavItems.map((item) => (
          <NavButton key={item.target} tab={tab} target={item.target} setTab={setTab} icon={item.icon} label={item.label} compact />
        ))}
      </nav>
      <FloatingCompassHelp
        profileComplete={profileComplete}
        hasUploads={hasUploads}
        hasOpportunities={hasOpportunities}
        isAdmin={isAdmin}
        setTab={setTab}
      />
      <NotificationBar notice={notice} onClose={() => setNotice(null)} />
      <ConfirmationToast confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </main>
  );
}

function AuthScreen({
  setOutput,
  notify,
  notice,
  clearNotice,
}: {
  setOutput: (value: unknown) => void;
  notify: (kind: "success" | "error", message: string) => void;
  notice: Notice;
  clearNotice: () => void;
}) {
  const [mode, setMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      if (!supabase) throw new Error("Compass auth is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
      if (mode === "forgot") {
        const { error } = await supabase.auth.resetPasswordForEmail(email);
        if (error) throw error;
        setMessage("Password reset instructions sent. Check your inbox.");
        setOutput({ password_reset_requested: true, email });
        notify("success", "Password reset instructions sent.");
        return;
      }
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: fullName ? { data: { full_name: fullName } } : undefined,
        });
        if (error) throw error;
        if (data.session) {
          sessionStorage.setItem(ONBOARDING_KEY, "1");
        }
        setMessage(
          data.session
            ? "Account created. Complete your profile next."
            : "Account created. Check your email to confirm your account.",
        );
        setOutput({ account_created: true, email });
        notify(
          "success",
          data.session ? "Account created. Add your student details next." : "Account created. Check your email to confirm it.",
        );
        return;
      }
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      setMessage("Signed in.");
      setOutput({ signed_in: Boolean(data.session), email });
      notify("success", "Signed in successfully.");
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  const authTitle = mode === "signin" ? "Welcome back" : mode === "signup" ? "Create workspace" : "Reset password";
  const authText = mode === "signin"
    ? "Sign in to continue your opportunity workspace."
    : mode === "signup"
      ? "Start a profile for scholarships, research roles, and application planning."
      : "Use your email to receive a secure password reset link.";
  const submitText = loading ? "Please wait..." : mode === "signin" ? "Sign in" : mode === "signup" ? "Create account" : "Send reset link";

  return (
    <>
      <div className="auth-loader" aria-label="Loading Compass">
        <div className="auth-dial">
          <svg className="loader-ring-one" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="68" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="0.6" />
            <line x1="70" y1="2" x2="70" y2="12" stroke="rgba(110,231,199,0.7)" strokeWidth="1.4" strokeLinecap="round" />
            <line x1="70" y1="128" x2="70" y2="138" stroke="rgba(255,255,255,0.2)" strokeWidth="0.8" strokeLinecap="round" />
            <line x1="2" y1="70" x2="12" y2="70" stroke="rgba(255,255,255,0.2)" strokeWidth="0.8" strokeLinecap="round" />
            <line x1="128" y1="70" x2="138" y2="70" stroke="rgba(255,255,255,0.2)" strokeWidth="0.8" strokeLinecap="round" />
            {[30, 60, 120, 150, 210, 240, 300, 330].map((degree) => (
              <line key={degree} x1="70" y1="2" x2="70" y2="8" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" transform={`rotate(${degree},70,70)`} />
            ))}
          </svg>
          <svg className="loader-ring-two" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="52" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" strokeDasharray="4 6" />
          </svg>
          <svg viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="60" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
            <circle className="loader-arc-sweep" cx="70" cy="70" r="60" />
            <circle className="loader-crosshair-ring" cx="70" cy="70" r="20" />
          </svg>
          <svg viewBox="0 0 140 140">
            <text x="70" y="14" textAnchor="middle" fontSize="9" fill="rgba(110,231,199,0.85)" fontFamily="system-ui" fontWeight="500" letterSpacing="0.5">N</text>
            <text x="70" y="135" textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.22)" fontFamily="system-ui">S</text>
            <text x="133" y="73" textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.22)" fontFamily="system-ui">E</text>
            <text x="7" y="73" textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.22)" fontFamily="system-ui">W</text>
            <g className="loader-needle">
              <polygon points="70,18 73,66 70,70 67,66" fill="#6ee7c7" />
              <polygon points="70,122 73,74 70,70 67,74" fill="rgba(255,255,255,0.13)" />
              <circle cx="70" cy="70" r="5.5" fill="#07080f" stroke="rgba(110,231,199,0.55)" strokeWidth="1.2" />
              <circle cx="70" cy="70" r="2" fill="#6ee7c7" />
            </g>
          </svg>
        </div>
        <div className="auth-loader-title">COMPASS</div>
        <div className="auth-loader-sub">Opportunity workspace</div>
        <div className="auth-loader-line" />
      </div>

      <div className="auth-page">
        <section className="auth-visual-pane">
        <div className="auth-brand-block">
          <div className="auth-wordmark">Compass</div>
          <div className="auth-tagline">Scholarships, research, and applications</div>
          <div className="auth-hero-copy">
            <h1>Navigate scholarships, research, and applications with clarity.</h1>
            <p>Find verified programs, prepare grounded documents, and keep every deadline moving in one focused workspace.</p>
          </div>
        </div>

        <div className="auth-route-stage" aria-label="Compass opportunity route map">
          <svg className="auth-route-svg" viewBox="0 0 760 280" preserveAspectRatio="none">
            <path className="auth-route-dash" d="M84 176 C 188 72, 258 68, 344 104 S 548 214, 664 72" />
            <path className="auth-route-line" d="M84 176 C 188 72, 258 68, 344 104 S 548 214, 664 72" />
          </svg>
          <span className="auth-node n1" />
          <span className="auth-node n2" />
          <span className="auth-node n3" />
          <span className="auth-node n4" />
          <div className="auth-node-label l1">Profile <small>student context</small></div>
          <div className="auth-node-label l2">Verified sources <small>official pages first</small></div>
          <div className="auth-node-label l3">Grounded drafts <small>CV, SOP, emails</small></div>
          <div className="auth-node-label l4">Deadline tracking <small>next actions ready</small></div>
          <div className="auth-mini-compass" />
        </div>

        <div className="auth-feature-grid">
          <article className="auth-feature-card">
            <ShieldCheck size={18} />
            <h3>Verified discovery</h3>
            <p>Prioritize official pages and trusted sources before adding listings to your workspace.</p>
          </article>
          <article className="auth-feature-card">
            <FileText size={18} />
            <h3>Grounded documents</h3>
            <p>Use your profile and uploaded files to draft stronger SOPs, letters, and emails.</p>
          </article>
          <article className="auth-feature-card">
            <Bell size={18} />
            <h3>Deadline movement</h3>
            <p>Turn saved opportunities into a clear application path with reminders and next steps.</p>
          </article>
        </div>
      </section>

      <section className="auth-pane">
        <form className={`auth-panel auth-card ${mode === "signup" ? "create-mode" : ""} ${mode === "forgot" ? "forgot-mode" : ""}`.trim()} onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <div className="auth-eyebrow">Compass account</div>
          <h2 className="auth-title">{authTitle}</h2>
          <p className="auth-text">{authText}</p>

          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button type="button" className={`auth-tab ${mode === "signin" ? "active" : ""}`} onClick={() => setMode("signin")}>Sign in</button>
            <button type="button" className={`auth-tab ${mode === "signup" ? "active" : ""}`} onClick={() => setMode("signup")}>Create account</button>
          </div>

          {mode === "forgot" && <div className="auth-reset-help">Enter your account email and Compass will send instructions to reset your password.</div>}

          <div className="auth-field-group">
            {mode === "signup" && (
              <label className="auth-field">Full name
                <span className="auth-input-wrap"><User size={17} /><input value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Your full name" /></span>
              </label>
            )}
            <label className="auth-field">Email
              <span className="auth-input-wrap"><Mail size={17} /><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="your@email.com" /></span>
            </label>
            {mode !== "forgot" && (
              <label className="auth-field">Password
                <span className="auth-input-wrap"><LockKeyhole size={17} /><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password" /></span>
              </label>
            )}
          </div>

          {mode !== "forgot" && (
            <div className="auth-row-between">
              <label className="auth-check-line"><input type="checkbox" defaultChecked />Remember this device</label>
              <button type="button" className="auth-link-button" onClick={() => setMode("forgot")}>Forgot password?</button>
            </div>
          )}

          <button className="auth-primary-button" type="submit" disabled={!email || (mode !== "forgot" && !password) || loading}>
            {loading && <Spinner />}
            {submitText}
          </button>
          {mode === "forgot" && <button type="button" className="auth-back-button" onClick={() => setMode("signin")}>Back to sign in</button>}

          <div className="auth-security-line">
            <LockKeyhole size={14} />
            <span>Your workspace keeps profile details, documents, and application notes organized for opportunity matching.</span>
          </div>

          <div className="auth-fine-print">
            By continuing, you agree to use Compass for verified opportunity discovery, document preparation, and application tracking.
          </div>
        </form>
        {message && <p className="message">{message}</p>}
      </section>
      </div>
    </>
  );
}

function AccountPanel({
  profileForm,
  setProfileForm,
  saveProfile,
  loadProfile,
  profileLoaded,
  isNewAccount,
  profileComplete,
  compassUserId,
  setTab,
  loading,
}: {
  profileForm: StudentProfile;
  setProfileForm: (value: StudentProfile) => void;
  saveProfile: () => Promise<void>;
  loadProfile: () => Promise<void>;
  profileLoaded: boolean;
  isNewAccount: boolean;
  profileComplete: boolean;
  compassUserId: string;
  setTab: (tab: Tab) => void;
  loading: Partial<Record<LoadingKey, boolean>>;
}) {
  const updateField = <K extends keyof StudentProfile>(key: K, value: StudentProfile[K]) => {
    setProfileForm({ ...profileForm, [key]: value });
  };

  return (
    <div className="panel-stack">
      {isNewAccount && (
        <div className="panel account-welcome">
          <PanelHeader title="Welcome to Compass" meta="Set up your student profile to get started" />
          <p className="muted-text">
            Compass uses your academic background, skills, and goals to plan searches, check eligibility, and rank
            opportunities. Fill in the details below, then start searching.
          </p>
        </div>
      )}

      <div className="panel">
        <PanelHeader
          title="Student profile"
          meta={profileComplete ? "Profile ready for search and matching" : "Country, degree, and field are required"}
          action={
            <button onClick={loadProfile} disabled={loading.profile}>
              {loading.profile ? <Spinner /> : <User size={16} />} Reload
            </button>
          }
        />

        {!profileLoaded && <SkeletonBlock lines={4} />}

        {compassUserId && (
          <div className="account-id-banner">
            <span>Your Compass user ID</span>
            <strong className="mono-id">{compassUserId}</strong>
          </div>
        )}

        <section className="account-section">
          <h4>About you</h4>
          <div className="form-grid">
            <label>
              Full name
              <span className="field-help">Used to personalize documents and application drafts.</span>
              <input
                value={profileForm.full_name ?? ""}
                onChange={(event) => updateField("full_name", event.target.value || null)}
                placeholder="Ayesha Khan"
              />
            </label>
            <label>
              Country
              <span className="field-help">Required for nationality, residency, and country-specific eligibility checks.</span>
              <input
                value={profileForm.country ?? ""}
                onChange={(event) => updateField("country", event.target.value || null)}
                placeholder="Pakistan"
                required
              />
            </label>
            <label>
              Degree
              <span className="field-help">Required so Compass can match your current or target study level.</span>
              <input
                value={profileForm.degree ?? ""}
                onChange={(event) => updateField("degree", event.target.value || null)}
                placeholder="BS Data Science"
                required
              />
            </label>
            <label>
              Field of study
              <span className="field-help">Required for finding programs and roles that match your academic area.</span>
              <input
                value={profileForm.field ?? ""}
                onChange={(event) => updateField("field", event.target.value || null)}
                placeholder="Artificial Intelligence"
                required
              />
            </label>
            <label>
              Semester / year
              <span className="field-help">Helps separate internships, exchange programs, masters, and graduate schemes.</span>
              <input
                value={profileForm.semester ?? ""}
                onChange={(event) => updateField("semester", event.target.value || null)}
                placeholder="Final year"
              />
            </label>
            <label>
              CGPA (0–4)
              <span className="field-help">Used only when listings include GPA or merit requirements.</span>
              <input
                type="number"
                min="0"
                max="4"
                step="0.01"
                value={profileForm.cgpa ?? ""}
                onChange={(event) =>
                  updateField("cgpa", event.target.value === "" ? null : Number(event.target.value))
                }
                placeholder="3.8"
              />
            </label>
          </div>
        </section>

        <section className="account-section">
          <h4>Skills and preferences</h4>
          <div className="form-grid">
            <TagListInput
              className="full-width"
              label="Skills"
              hint="Press Enter or click Add for each skill"
              values={profileForm.skills}
              onChange={(skills) => updateField("skills", skills)}
              placeholder="e.g. Python"
            />
            <TagListInput
              className="full-width"
              label="Preferred countries"
              hint="Add each country separately"
              values={profileForm.preferred_countries}
              onChange={(preferred_countries) => updateField("preferred_countries", preferred_countries)}
              placeholder="e.g. Germany"
            />
            <TagListInput
              className="full-width"
              label="Preferred regions"
              hint="Add each region separately"
              values={profileForm.preferred_regions}
              onChange={(preferred_regions) => updateField("preferred_regions", preferred_regions)}
              placeholder="e.g. Europe"
            />
            <TagListInput
              className="full-width"
              label="Opportunity types"
              hint="Add scholarship types, programs, or roles you want"
              values={profileForm.preferred_opportunity_types}
              onChange={(preferred_opportunity_types) =>
                updateField("preferred_opportunity_types", preferred_opportunity_types)
              }
              placeholder="e.g. fully funded masters"
            />
            <label>
              Budget preference
              <span className="field-help">Helps rank fully funded, partial funding, and self-funded options correctly.</span>
              <select
                value={profileForm.budget_preference ?? ""}
                onChange={(event) => updateField("budget_preference", event.target.value || null)}
              >
                <option value="">Select...</option>
                <option value="Fully funded only">Fully funded only</option>
                <option value="Partial funding acceptable">Partial funding acceptable</option>
                <option value="Self-funded">Self-funded</option>
              </select>
            </label>
          </div>
        </section>

        <section className="account-section">
          <h4>Tests and goals</h4>
          <div className="form-grid">
            <label>
              IELTS status
              <span className="field-help">Flags language-test requirements early so you can plan before deadlines.</span>
              <select
                value={profileForm.ielts_status ?? ""}
                onChange={(event) => updateField("ielts_status", event.target.value || null)}
              >
                <option value="">Select...</option>
                <option value="Not taken">Not taken</option>
                <option value="Scheduled">Scheduled</option>
                <option value="Completed">Completed</option>
                <option value="Waived">Waived</option>
              </select>
            </label>
            <label>
              GRE status
              <span className="field-help">Helps identify programs where GRE is required, waived, or optional.</span>
              <select
                value={profileForm.gre_status ?? ""}
                onChange={(event) => updateField("gre_status", event.target.value || null)}
              >
                <option value="">Select...</option>
                <option value="Not taken">Not taken</option>
                <option value="Scheduled">Scheduled</option>
                <option value="Completed">Completed</option>
                <option value="Not required">Not required</option>
              </select>
            </label>
            <label className="full-width">
              Career goal
              <span className="field-help">Gives Compass context for ranking and document generation.</span>
              <textarea
                className="compact-textarea"
                value={profileForm.career_goal ?? ""}
                onChange={(event) => updateField("career_goal", event.target.value || null)}
                placeholder="Pursue a fully funded MS in AI and work on applied ML research."
              />
            </label>
          </div>
        </section>

        <div className="button-row">
          <button
            className="primary-button"
            onClick={saveProfile}
            disabled={loading.profile || !profileForm.country?.trim() || !profileForm.degree?.trim() || !profileForm.field?.trim()}
          >
            {loading.profile ? <Spinner /> : <User size={16} />}
            {loading.profile ? "Saving..." : "Save profile"}
          </button>
          {profileComplete && (
            <button onClick={() => setTab("search")}>
              <Search size={16} /> Go to search
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchPanel({
  profile,
  profileComplete,
  hasUploads,
  setTab,
  query,
  debouncedQuery,
  setQuery,
  runSearch,
  searchJob,
  searchSummary,
  discoveredOpportunities,
  onViewDetails,
  cancelSearch,
  retrySearch,
  searchJobs,
  refreshSearchJobs,
  onCancelSearchJob,
  onRetrySearchJob,
  onDeleteSearchJob,
  loading,
}: {
  profile: StudentProfile | null;
  profileComplete: boolean;
  hasUploads: boolean;
  setTab: (tab: Tab) => void;
  query: string;
  debouncedQuery: string;
  setQuery: (value: string) => void;
  runSearch: () => Promise<void>;
  searchJob: SearchJob | null;
  searchSummary: SearchResultPayload | null;
  discoveredOpportunities: OpportunityRecord[];
  onViewDetails: (item: OpportunityRecord) => void;
  cancelSearch: () => Promise<void>;
  retrySearch: () => Promise<void>;
  searchJobs: SearchJob[];
  refreshSearchJobs: () => Promise<void>;
  onCancelSearchJob: (job: SearchJob) => Promise<void>;
  onRetrySearchJob: (job: SearchJob) => Promise<void>;
  onDeleteSearchJob: (job: SearchJob) => Promise<void>;
  loading: Partial<Record<LoadingKey, boolean>>;
}) {
  const searchSettling = query.trim() !== debouncedQuery.trim();
  const activeSearch = searchJob && ["queued", "running"].includes(searchJob.status);
  const sourceCount = searchSummary?.raw_result_count ?? discoveredOpportunities.length ?? 0;
  const recommendedSearches = [
    {
      title: "Fully funded data science masters scholarships in Australia",
      detail: "Best when you want funding-first results",
    },
    {
      title: "AI research internships for final-year undergraduate students",
      detail: "Good for research experience before a masters",
    },
    {
      title: "Erasmus Mundus programs related to machine learning",
      detail: "Useful for multi-country European programs",
    },
  ];
  return (
    <div className="template-page search-template-page">
      <section className="template-header">
        <p>Search smarter by combining your student profile, uploaded documents, official sources, and deadline signals.</p>
      </section>
      <div className="template-body">
        <div className="template-workspace">
          <div className="template-stack">
            <div className="template-card">
              <div className="template-card-title">Student profile</div>
              <div className="template-card-subtitle">Used for matching, filtering, and eligibility reasoning</div>
              <div className="template-status-list search-profile-status">
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Academic background</div><div className="template-status-sub">Degree, field, CGPA, university</div></div><div className={`template-status-value ${profileComplete ? "" : "warn-value"}`}>{profileComplete ? "Ready" : "Needs detail"}</div></div>
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Target preferences</div><div className="template-status-sub">Countries, degree level, funding type</div></div><div className="template-status-value warn-value">{profile?.preferred_countries?.length || profile?.budget_preference ? "Partial" : "Needs detail"}</div></div>
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Document context</div><div className="template-status-sub">CV, transcript, certificates</div></div><div className={`template-status-value ${hasUploads ? "" : "muted-value"}`}>{hasUploads ? "Loaded" : "Not loaded"}</div></div>
              </div>
              <textarea className="template-input search-profile-text" readOnly value={profileSummary(profile)} placeholder="Describe your background, field of study, GPA, skills, nationality, preferred countries, research interests, and funding needs" />
              <div className="template-actions">
                <button className="template-btn template-btn-dark" onClick={() => setTab("account")}><Settings size={16} /> {profileComplete ? "Update profile" : "Complete profile"}</button>
              </div>
              {!profileComplete && <div className="template-mini-note search-warning">Add your country, degree, and field of study before searching.</div>}
              {profileComplete && !hasUploads && (
                <div className="template-mini-note">
                  Upload your CV next so Compass can use your real experience when ranking matches.
                  <button type="button" className="inline-action" onClick={() => setTab("uploads")}>Upload your CV</button>
                </div>
              )}
            </div>

            <div className="template-card">
              <div className="template-card-title">Find opportunities</div>
              <div className="template-card-subtitle">Search official pages, trusted aggregators, research labs, and funding bodies</div>
              <div className="template-command">
                <input
                  className="template-input"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Find fully funded AI scholarships in Europe for Pakistani students"
                />
                <button className="template-btn template-btn-green" onClick={runSearch} disabled={!query.trim() || loading.search}>
                  {loading.search ? <Spinner /> : <Search size={16} />}
                  {loading.search ? "Searching..." : "Search"}
                </button>
              </div>
              {query && <div className="debounce-status">{searchSettling ? "Preparing search..." : `Ready to search: ${debouncedQuery}`}</div>}
              <div className="search-scope-block">
                <div className="template-label">Search scope</div>
                <div className="template-check-grid">
                  <label className="template-check-item"><input type="checkbox" defaultChecked /> Official university pages</label>
                  <label className="template-check-item"><input type="checkbox" defaultChecked /> Scholarship portals</label>
                  <label className="template-check-item"><input type="checkbox" /> Research lab pages</label>
                  <label className="template-check-item"><input type="checkbox" /> Government funding pages</label>
                </div>
              </div>
              {loading.search && <SkeletonBlock lines={5} />}
              {searchJob && (
                <div className="job-progress">
                  {["queued", "running"].includes(searchJob.status) && (
                    <button onClick={cancelSearch} disabled={loading.search}><X size={16} /> Cancel</button>
                  )}
                  {["failed", "cancelled"].includes(searchJob.status) && (
                    <button onClick={retrySearch} disabled={loading.search}><Search size={16} /> Retry</button>
                  )}
                </div>
              )}
              {searchSummary?.answer && (
                <div className="search-answer">
                  <strong>Search summary</strong>
                  <p>{searchSummary.answer}</p>
                </div>
              )}
            </div>

            <div className="template-card">
              <div className="template-card-title">Recommended searches</div>
              <div className="template-card-subtitle">Clean prompt ideas that fit your profile and goals</div>
              <div className="template-status-list">
                {recommendedSearches.map((item) => (
                  <button className="template-rec-row" key={item.title} onClick={() => setQuery(item.title)}>
                    <div className="template-status-left"><div className="template-status-title">{item.title}</div><div className="template-status-sub">{item.detail}</div></div>
                    <span className="template-arrow">›</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <aside className="template-side">
            <div className="template-card">
              <div className="template-card-title">Discovery activity</div>
              <div className="template-card-subtitle">Live search state and reasoning signals</div>
              <div className="template-status-list">
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Current task</div><div className="template-status-sub">{searchJob?.progress_message || (query ? "Ready for search query" : "Waiting for a search query")}</div></div><div className={`template-status-value ${activeSearch ? "" : "muted-value"}`}>{activeSearch ? searchJob?.status : searchJob?.status || "Idle"}</div></div>
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Sources checked</div><div className="template-status-sub">Official and trusted pages</div></div><div className="template-status-value">{sourceCount}</div></div>
                <div className="template-status-row"><div className="template-status-left"><div className="template-status-title">Eligibility focus</div><div className="template-status-sub">Funding, country, degree level, GPA</div></div><div className="template-status-value">Profile</div></div>
              </div>
            </div>
            <div className="template-card">
              <div className="template-card-title">Next best action</div>
              <div className="template-card-subtitle">Improve matching before running a broad search</div>
              <div className="template-mini-note">Add preferred countries, target degree level, English test status, and funding preference. This helps Compass rank results by real eligibility instead of only keyword similarity.</div>
            </div>
          </aside>
        </div>

        {discoveredOpportunities.length > 0 && (
          <div className="template-card">
            <div className="template-card-title">Latest results</div>
            <div className="template-card-subtitle">{discoveredOpportunities.length} opportunit{discoveredOpportunities.length === 1 ? "y" : "ies"} found</div>
            <div className="opportunity-list">
              {discoveredOpportunities.map((item, index) => (
                <OpportunityCard
                  key={item.id ?? `${item.title}-${index}`}
                  item={item}
                  actions={<div className="button-row"><button onClick={() => onViewDetails(item)}><FileText size={16} /> View details</button></div>}
                />
              ))}
            </div>
          </div>
        )}

        {!loading.search && !searchJob && discoveredOpportunities.length === 0 && (
          <EmptyState
            title="Run your first scholarship search"
            detail="Start with a focused query and Compass will check trusted sources, eligibility, deadlines, and fit."
            action={<button className="primary-button" onClick={() => setQuery("Fully funded scholarships for my field")}><Search size={16} /> Use starter search</button>}
          />
        )}
        <SearchHistoryPanel
          jobs={searchJobs}
          onRefresh={refreshSearchJobs}
          onCancel={onCancelSearchJob}
          onRetry={onRetrySearchJob}
          onDelete={onDeleteSearchJob}
          loading={loading.workspace || loading.search}
        />
      </div>
    </div>
  );
}

function TagListInput({
  label,
  hint,
  values,
  onChange,
  placeholder,
  className,
}: {
  label: string;
  hint?: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState("");

  const addItems = (raw: string) => {
    const incoming = splitListInput(raw.replace(/\n/g, ","));
    if (!incoming.length) return;
    onChange(mergeListItems(values, incoming));
    setDraft("");
  };

  const removeItem = (index: number) => {
    onChange(values.filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <div className={`tag-list-field ${className ?? ""}`.trim()}>
      <span className="tag-list-label">{label}</span>
      {hint && <span className="tag-list-hint">{hint}</span>}
      <div className="tag-list-box">
        {values.map((value, index) => (
          <span className="tag-chip" key={`${value}-${index}`}>
            {value}
            <button
              type="button"
              className="tag-chip-remove"
              onClick={() => removeItem(index)}
              aria-label={`Remove ${value}`}
            >
              <X size={14} />
            </button>
          </span>
        ))}
        <div className="tag-list-input-row">
          <input
            className="tag-list-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addItems(draft);
              } else if (event.key === "Backspace" && !draft && values.length > 0) {
                removeItem(values.length - 1);
              }
            }}
            onBlur={() => {
              if (draft.trim()) addItems(draft);
            }}
            onPaste={(event) => {
              const pasted = event.clipboardData.getData("text");
              if (!pasted.includes(",") && !pasted.includes("\n")) return;
              event.preventDefault();
              addItems(pasted);
            }}
            placeholder={values.length ? "Add another..." : placeholder}
          />
          <button
            type="button"
            className="tag-list-add"
            onClick={() => addItems(draft)}
            disabled={!draft.trim()}
            aria-label={`Add ${label}`}
          >
            <Plus size={16} /> Add
          </button>
        </div>
      </div>
    </div>
  );
}

function NavButton({
  tab,
  target,
  setTab,
  icon,
  label,
  compact = false,
}: {
  tab: Tab;
  target: Tab;
  setTab: (tab: Tab) => void;
  icon: React.ReactNode;
  label: string;
  compact?: boolean;
}) {
  return (
    <button className={tab === target ? "active" : ""} onClick={() => setTab(target)} title={compact ? label : undefined}>
      {icon} <span>{label}</span>
    </button>
  );
}

function formatOpportunityDeadline(deadline?: string | null): string {
  if (!deadline) return "—";
  const parsed = new Date(deadline);
  if (Number.isNaN(parsed.getTime())) return deadline;
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatFundingLabel(funding?: string | null): string {
  if (!funding) return "—";
  const normalized = funding.toLowerCase();
  if (normalized.includes("full")) return "Full";
  if (normalized.includes("partial")) return "Partial or full";
  if (normalized.includes("stipend")) return "Stipend";
  return formatDisplayValue(funding);
}

function opportunityMatchScore(item: OpportunityRecord): number | null {
  if (typeof item.eligibility_result?.score === "number") return normalizePercentScore(item.eligibility_result.score);
  if (typeof item.priority_score === "number") return normalizePercentScore(item.priority_score);
  return null;
}

function normalizePercentScore(score: number): number {
  return score <= 1 ? score * 100 : score;
}

function isStrongMatch(item: OpportunityRecord): boolean {
  const score = opportunityMatchScore(item);
  return score !== null && score >= 70;
}

function isDeadlineSoon(deadline?: string | null, withinDays = 45): boolean {
  if (!deadline) return false;
  const parsed = new Date(deadline);
  if (Number.isNaN(parsed.getTime())) return false;
  const diff = parsed.getTime() - Date.now();
  return diff >= 0 && diff <= withinDays * 24 * 60 * 60 * 1000;
}

function needsOpportunityReview(item: OpportunityRecord): boolean {
  if ((item.warnings?.length ?? 0) > 0) return true;
  if ((item.verification?.risk_flags?.length ?? 0) > 0) return true;
  if (item.eligibility_result?.eligible === false) return true;
  if ((item.eligibility_result?.missing_requirements?.length ?? 0) > 0) return true;
  return false;
}

function deadlineRiskLabel(item: OpportunityRecord): string {
  if (item.eligibility_result?.deadline_passed) return "High";
  if (isDeadlineSoon(item.deadline, 14)) return "High";
  if (isDeadlineSoon(item.deadline, 45)) return "Medium";
  return "Low";
}

function deadlineVerificationLabel(item: OpportunityRecord): string {
  const verification = item.verification?.deadline_verification;
  if (!verification) return item.deadline ? "Extracted" : "Not verified";
  if (verification.status === "not_found") return "Not found";
  return verification.confidence_label || (verification.confidence && verification.confidence >= 0.8 ? "High" : "Medium");
}

function deadlineSourceLabel(sourceType?: string): string {
  return (sourceType || "unknown").replace(/_/g, " ");
}

function nextOpportunityAction(item: OpportunityRecord, isSaved: boolean): string {
  if (!isSaved) return "Save to list";
  if ((item.required_documents?.length ?? 0) > 0) return `Upload ${formatDisplayValue(item.required_documents?.[0])}`;
  if (needsOpportunityReview(item)) return "Review eligibility";
  return "View details";
}

function mergeOpportunityLists(saved: OpportunityRecord[], discovered: OpportunityRecord[]): OpportunityRecord[] {
  const merged = new Map<string, OpportunityRecord>();
  for (const item of [...discovered, ...saved]) {
    const key = item.id ?? `${item.title}-${item.provider}-${item.country}`;
    const existing = merged.get(key);
    merged.set(key, existing ? { ...existing, ...item } : item);
  }
  return Array.from(merged.values());
}

function HoloTiltCard({ children }: { children: React.ReactNode }) {
  const childRef = React.useRef<HTMLDivElement>(null);

  return (
    <div
      className="atlas-card atlas-tilt-card"
      onPointerMove={(event) => {
        const child = childRef.current;
        if (!child) return;
        const rect = event.currentTarget.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width - 0.5) * 12;
        const y = ((event.clientY - rect.top) / rect.height - 0.5) * -12;
        child.style.transform = `rotateY(${x}deg) rotateX(${y}deg)`;
      }}
      onPointerLeave={() => {
        const child = childRef.current;
        if (child) child.style.transform = "rotateY(0) rotateX(0)";
      }}
    >
      <div className="atlas-card-inner">
        <div className="atlas-card-title">Selected opportunity</div>
        <div className="atlas-card-subtitle">Match signals, eligibility, and next action for the selected listing.</div>
        <div className="holo-card" ref={childRef}>
          {children}
        </div>
      </div>
    </div>
  );
}

function OpportunityPanel({
  token,
  setOutput,
  runAction,
  loading,
  discoveredOpportunities,
  onViewDetails,
  setTab,
}: PanelProps & {
  discoveredOpportunities: OpportunityRecord[];
  onViewDetails: (item: OpportunityRecord) => void;
  setTab: (tab: Tab) => void;
}) {
  const [items, setItems] = useState<OpportunityRecord[]>([]);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const syncSavedIds = (opportunities: OpportunityRecord[]) => {
    const ids = new Set<string>();
    for (const item of opportunities) {
      if (item.id) ids.add(item.id);
    }
    setSavedIds(ids);
  };

  const load = async () => {
    await runAction("opportunities", "Loading your saved opportunities...", async () => {
      const result = await api("/opportunities", token);
      const opportunities = result.opportunities ?? [];
      setItems(opportunities);
      syncSavedIds(opportunities);
      setOutput(result);
    }, "Saved opportunities loaded.");
  };

  useEffect(() => {
    void load();
  }, [token]);

  const allItems = useMemo(
    () => mergeOpportunityLists(items, discoveredOpportunities),
    [items, discoveredOpportunities],
  );

  const itemKey = (item: OpportunityRecord) => item.id ?? `${item.title}-${item.provider}-${item.country}`;

  useEffect(() => {
    if (allItems.length === 0) {
      setSelectedKey(null);
      return;
    }
    if (!selectedKey || !allItems.some((item) => itemKey(item) === selectedKey)) {
      setSelectedKey(itemKey(allItems[0]));
    }
  }, [allItems, selectedKey]);

  const selectedItem = allItems.find((item) => itemKey(item) === selectedKey) ?? allItems[0] ?? null;
  const selectedIsSaved = selectedItem?.id ? savedIds.has(selectedItem.id) : false;

  const stats = useMemo(() => ({
    saved: items.length,
    strongMatches: allItems.filter(isStrongMatch).length,
    deadlinesSoon: allItems.filter((item) => isDeadlineSoon(item.deadline)).length,
    needReview: allItems.filter(needsOpportunityReview).length,
  }), [allItems, items.length]);

  const unsaveOpportunity = async (item: OpportunityRecord) => {
    if (!item.id) return;
    await runAction("opportunities", "Removing opportunity from your saved list...", async () => {
      const result = await api(`/opportunities/${item.id}/save`, token, { method: "DELETE" });
      setSavedIds((current) => {
        const next = new Set(current);
        next.delete(item.id!);
        return next;
      });
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setOutput(result);
    }, "Removed from your saved list.");
  };

  const saveOpportunity = async (item: OpportunityRecord) => {
    await runAction("opportunities", "Saving opportunity to your account...", async () => {
      const result = item.id
        ? await api(`/opportunities/${item.id}/save`, token, { method: "POST", body: "{}" })
        : await api("/opportunities/save", token, {
            method: "POST",
            body: JSON.stringify({ opportunity: item }),
          });
      const saved = result.saved as {
        saved_id: string;
        opportunity_id: string;
        opportunity: OpportunityRecord;
      };
      const merged = {
        ...saved.opportunity,
        saved_id: saved.saved_id,
        source_tier: item.source_tier ?? saved.opportunity.source_tier,
        verification: item.verification ?? saved.opportunity.verification,
        eligibility_result: item.eligibility_result ?? saved.opportunity.eligibility_result,
      };
      setSavedIds((current) => new Set([...current, saved.opportunity_id]));
      setItems((current) => {
        const withoutDuplicate = current.filter((entry) => entry.id !== saved.opportunity_id);
        return [merged, ...withoutDuplicate];
      });
      setOutput(result);
    }, "Saved to your account.");
  };

  return (
    <div className="atlas-page">
      <section className="atlas-header">
        <p>Matched and saved opportunities are organized like a serious decision database.</p>
      </section>

      <div className="atlas-body">
        <div className="atlas-cards-4">
          <div className="atlas-stat"><div className="v">{stats.saved}</div><div className="l">Saved</div></div>
          <div className="atlas-stat"><div className="v">{stats.strongMatches}</div><div className="l">Strong matches</div></div>
          <div className="atlas-stat"><div className="v">{stats.deadlinesSoon}</div><div className="l">Deadlines soon</div></div>
          <div className="atlas-stat"><div className="v">{stats.needReview}</div><div className="l">Need review</div></div>
        </div>

        <div className="atlas-layout">
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Opportunity list</div>
              <div className="atlas-card-subtitle">All saved and discovered opportunities. Select a row to preview match details.</div>
              {loading.opportunities && <SkeletonBlock lines={5} />}
              {!loading.opportunities && allItems.length === 0 && (
                <EmptyState
                  title="Save an opportunity to start tracking"
                  detail="Run a search, review the strongest matches, then save the ones you want to compare and track."
                  action={<button className="atlas-btn atlas-btn-green" onClick={() => setTab("search")}><Search size={16} /> Start search</button>}
                />
              )}
              {allItems.length > 0 && (
                <div className="atlas-table-wrap">
                  <table className="atlas-table">
                    <thead>
                      <tr>
                        <th>Opportunity</th>
                        <th>ID</th>
                        <th>Country</th>
                        <th>Deadline</th>
                        <th>Funding</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allItems.map((item) => {
                        const key = itemKey(item);
                        const isSelected = key === selectedKey;
                        return (
                          <tr
                            key={key}
                            className={isSelected ? "selected" : ""}
                            onClick={() => setSelectedKey(key)}
                          >
                            <td><b>{item.title || "Untitled opportunity"}</b></td>
                            <td className="mono-id">{item.id ?? "—"}</td>
                            <td>{formatDisplayValue(item.country)}</td>
                            <td>{formatOpportunityDeadline(item.deadline)}</td>
                            <td>{formatFundingLabel(item.funding_type)}</td>
                            <td>
                              <button
                                className="atlas-table-action"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onViewDetails(item);
                                }}
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="atlas-actions">
                <button className="atlas-btn atlas-btn-dark" onClick={load} disabled={loading.opportunities}>
                  {loading.opportunities ? <Spinner /> : <Search size={16} />} {loading.opportunities ? "Loading..." : "Refresh saved"}
                </button>
              </div>
            </div>
          </div>

          {selectedItem ? (
            <HoloTiltCard>
              <div className="atlas-card-title">{selectedItem.title || "Untitled opportunity"}</div>
              <div className="atlas-card-subtitle">
                {selectedItem.summary || "Profile match and eligibility signals appear here for the selected listing."}
              </div>
              <div className="atlas-status-row">
                <b>Compass score</b>
                <span>{opportunityMatchScore(selectedItem) !== null ? `${Math.round(opportunityMatchScore(selectedItem)!)}%` : "—"}</span>
              </div>
              <div className="atlas-status-row">
                <b>Deadline risk</b>
                <span>{deadlineRiskLabel(selectedItem)}</span>
              </div>
              <div className="atlas-status-row">
                <b>Deadline confidence</b>
                <span>{deadlineVerificationLabel(selectedItem)}</span>
              </div>
              <div className="atlas-status-row">
                <b>Funding</b>
                <span>{formatFundingLabel(selectedItem.funding_type)}</span>
              </div>
              <div className="atlas-status-row">
                <b>Next action</b>
                <span>{nextOpportunityAction(selectedItem, selectedIsSaved)}</span>
              </div>
              <div className="atlas-actions">
                <button className="atlas-btn atlas-btn-green" onClick={() => onViewDetails(selectedItem)}>
                  <FileText size={16} /> View details
                </button>
                {selectedIsSaved ? (
                  <button className="atlas-btn atlas-btn-dark" onClick={() => unsaveOpportunity(selectedItem)} disabled={loading.opportunities}>
                    <BookmarkMinus size={16} /> Unsave
                  </button>
                ) : (
                  <button className="atlas-btn atlas-btn-dark" onClick={() => saveOpportunity(selectedItem)} disabled={loading.opportunities}>
                    <BookmarkPlus size={16} /> Save
                  </button>
                )}
              </div>
            </HoloTiltCard>
          ) : (
            <div className="atlas-card">
              <div className="atlas-card-inner">
                <div className="atlas-card-title">Selected opportunity</div>
                <div className="atlas-card-subtitle">Choose a row from the list to preview match signals and next actions.</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OpportunityCard({
  item,
  actions,
  defaultExpanded = false,
}: {
  item: OpportunityRecord;
  actions?: React.ReactNode;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const verification = item.verification ?? {};
  const deadlineVerification = verification.deadline_verification;
  const eligibility = item.eligibility_result ?? {};
  const applicationUrl = formatDisplayValue(item.application_url);
  const showUrl = applicationUrl !== "Not listed" && applicationUrl.startsWith("http");

  return (
    <motion.article
      className="opportunity-card detailed"
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="opportunity-card-top">
        <div className="opportunity-signals">
          <div>
            <span>Source tier</span>
            <strong>{formatDisplayValue(item.source_tier || verification.source_tier)}</strong>
          </div>
          <div>
            <span>Trust</span>
            <strong>{trustLabel(verification.trust_level)}</strong>
          </div>
          <div>
            <span>Fit</span>
            <strong>{item.priority ? `${item.priority} priority` : "Unranked"}</strong>
          </div>
        </div>
        <h3>{item.title || "Untitled opportunity"}</h3>
        <p className="opportunity-summary">{item.summary || "No summary available."}</p>
      </div>

      <div className="button-row">
        <button onClick={() => setExpanded((current) => !current)}>
          {expanded ? "Show less" : "Show more"}
        </button>
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="disclosure-content"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <dl className="opportunity-detail-grid">
              {item.id && (
                <div>
                  <dt>Opportunity ID</dt>
                  <dd className="mono-id">{item.id}</dd>
                </div>
              )}
              {item.saved_id && (
                <div>
                  <dt>Saved record ID</dt>
                  <dd className="mono-id">{item.saved_id}</dd>
                </div>
              )}
              <div>
                <dt>Provider</dt>
                <dd>{formatDisplayValue(item.provider)}</dd>
              </div>
              <div>
                <dt>Country / region</dt>
                <dd>{formatDisplayValue(item.country)}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{formatDisplayValue(item.opportunity_type)}</dd>
              </div>
              <div>
                <dt>Funding</dt>
                <dd>{formatDisplayValue(item.funding_type)}</dd>
              </div>
              <div>
                <dt>Application deadline</dt>
                <dd>{formatDeadline(item.deadline)}</dd>
              </div>
              <div>
                <dt>Deadline confidence</dt>
                <dd>{deadlineVerificationLabel(item)}</dd>
              </div>
              <div>
                <dt>Start date</dt>
                <dd>Not listed</dd>
              </div>
              <div>
                <dt>Contact</dt>
                <dd>{formatDisplayValue(item.contact_email)}</dd>
              </div>
              <div>
                <dt>Application link</dt>
                <dd>
                  {showUrl ? (
                    <a href={applicationUrl} target="_blank" rel="noreferrer">
                      {applicationUrl}
                    </a>
                  ) : (
                    applicationUrl
                  )}
                </dd>
              </div>
            </dl>

            <section className="opportunity-section">
              <h4>Eligibility criteria</h4>
              {item.eligibility && item.eligibility.length > 0 ? (
                <ul>
                  {item.eligibility.map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-text">No explicit eligibility criteria extracted from the source.</p>
              )}
            </section>

            <section className="opportunity-section">
              <h4>Profile match</h4>
              <p>
                <strong>{eligibility.eligible ? "Likely eligible" : "Eligibility unclear"}</strong>
                {typeof eligibility.score === "number" ? ` · Score ${Math.round(eligibility.score * 100)}%` : ""}
                {eligibility.deadline_passed ? " · Deadline appears passed" : ""}
              </p>
              {eligibility.reasons && eligibility.reasons.length > 0 && (
                <ul>
                  {eligibility.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}
              {eligibility.missing_requirements && eligibility.missing_requirements.length > 0 && (
                <>
                  <strong>Missing or unconfirmed requirements</strong>
                  <ul>
                    {eligibility.missing_requirements.map((entry) => (
                      <li key={entry}>{entry}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            {item.required_documents && item.required_documents.length > 0 && (
              <section className="opportunity-section">
                <h4>Required documents</h4>
                <ul>
                  {item.required_documents.map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="opportunity-section">
              <h4>Deadline verification</h4>
              {deadlineVerification ? (
                <>
                  <p>
                    Status: {deadlineVerification.status?.replace(/_/g, " ") || "unknown"} · Confidence: {deadlineVerificationLabel(item)}
                    {deadlineVerification.last_checked ? ` · Last checked ${formatDeadline(deadlineVerification.last_checked)}` : ""}
                  </p>
                  <p>
                    Source: {deadlineSourceLabel(deadlineVerification.source_type)}
                    {deadlineVerification.source_url ? " · " : ""}
                    {deadlineVerification.source_url && (
                      <a href={deadlineVerification.source_url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    )}
                  </p>
                  {deadlineVerification.applies_to && <p>Applies to: {deadlineVerification.applies_to}</p>}
                  {deadlineVerification.source_text && <p className="muted-text">Evidence: {deadlineVerification.source_text}</p>}
                  {deadlineVerification.note && <p className="muted-text">{deadlineVerification.note}</p>}
                </>
              ) : (
                <p className="muted-text">Deadline has not been deeply verified yet. Use Check Deadline for a targeted official-source search.</p>
              )}
            </section>

            <section className="opportunity-section">
              <h4>Source verification</h4>
              <p>
                Domain: {formatDisplayValue(verification.domain)} · Trust: {trustLabel(verification.trust_level)}
              </p>
              {verification.notes && verification.notes.length > 0 && (
                <ul>
                  {verification.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              )}
              {verification.risk_flags && verification.risk_flags.length > 0 && (
                <p className="warning-text">Risk flags: {verification.risk_flags.join(", ")}</p>
              )}
            </section>

            {item.warnings && item.warnings.length > 0 && (
              <section className="opportunity-section warning-block">
                <h4>Warnings</h4>
                <ul>
                  {item.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </section>
            )}

            {item.extraction_notes && item.extraction_notes.length > 0 && (
              <section className="opportunity-section">
                <h4>Extraction notes</h4>
                <ul>
                  {item.extraction_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </section>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {item.payment_requested && <p className="warning-text">This listing may request payment. Verify on the official source before proceeding.</p>}

      {actions}
    </motion.article>
  );
}

function OpportunityDetailPanel({
  item,
  token,
  setOutput,
  runAction,
  setTab,
  loading,
  refreshWorkspace,
}: PanelProps & {
  item: OpportunityRecord | null;
  setTab: (tab: Tab) => void;
  refreshWorkspace: () => Promise<void>;
}) {
  const [detailItem, setDetailItem] = useState<OpportunityRecord | null>(item);

  useEffect(() => {
    setDetailItem(item);
  }, [item]);

  if (!detailItem) {
    return (
      <div className="panel">
        <PanelHeader title="Opportunity detail" meta="No opportunity selected" />
        <p className="muted-text">Choose View details from search results or saved opportunities.</p>
        <button onClick={() => setTab("opportunities")}>
          <BookmarkPlus size={16} /> Back to opportunities
        </button>
      </div>
    );
  }

  const save = async () =>
    runAction("opportunities", "Saving opportunity to your account...", async () => {
      const result = detailItem.id
        ? await api(`/opportunities/${detailItem.id}/save`, token, { method: "POST", body: "{}" })
        : await api("/opportunities/save", token, { method: "POST", body: JSON.stringify({ opportunity: detailItem }) });
      setOutput(result);
    }, "Opportunity saved successfully.");

  const plan = async () => {
    if (!detailItem.id) return;
    await runAction("opportunities", "Creating deadline plan...", async () => {
      const result = await api(`/opportunities/${detailItem.id}/deadline-plan`, token, { method: "POST", body: "{}" });
      setOutput(result);
      await refreshWorkspace();
    }, "Deadline plan created successfully.");
  };

  const checkDeadline = async () => {
    if (!detailItem.id) return;
    await runAction("opportunities", "Checking official deadline sources...", async () => {
      const result = await api(`/opportunities/${detailItem.id}/verify-deadline`, token, { method: "POST", body: "{}" });
      if (result.opportunity) {
        setDetailItem(result.opportunity as OpportunityRecord);
      }
      setOutput(result);
      await refreshWorkspace();
    }, "Deadline check completed.");
  };

  return (
    <div className="panel-stack">
      <div className="panel detail-toolbar">
        <button onClick={() => setTab("opportunities")}>
          <BookmarkPlus size={16} /> Back to opportunities
        </button>
        <div className="button-row">
          <button onClick={save} disabled={loading.opportunities}>
            <BookmarkPlus size={16} /> Save
          </button>
          <button onClick={plan} disabled={!detailItem.id || loading.opportunities}>
            <CalendarClock size={16} /> Plan
          </button>
          <button onClick={checkDeadline} disabled={!detailItem.id || loading.opportunities}>
            <Search size={16} /> Check Deadline
          </button>
        </div>
      </div>
      <OpportunityCard item={detailItem} defaultExpanded />
    </div>
  );
}

function OpportunityIdField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: OpportunityRecord[];
}) {
  const savedIds = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    for (const item of options) {
      if (!item.id || seen.has(item.id)) continue;
      seen.add(item.id);
      list.push(item.id);
    }
    return list;
  }, [options]);

  return (
    <label>
      <span className="atlas-label">{label}</span>
      <div className="atlas-inline-field">
        <select className="atlas-input atlas-input-inline" value={value && savedIds.includes(value) ? value : ""} onChange={(event) => onChange(event.target.value || value)}>
          <option value="">Saved opportunity IDs</option>
          {savedIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        <input className="atlas-input" value={value} maxLength={8} onChange={(event) => onChange(event.target.value)} placeholder="OPP-102" />
      </div>
    </label>
  );
}

function TrackerPanel({
  token,
  setOutput,
  runAction,
  loading,
  setTab,
  hasOpportunities,
  tasks,
  refreshWorkspace,
  opportunityOptions,
  requestConfirmation,
}: PanelProps & {
  setTab: (tab: Tab) => void;
  hasOpportunities: boolean;
  tasks: ApplicationTaskRecord[];
  refreshWorkspace: () => Promise<void>;
  opportunityOptions: OpportunityRecord[];
  requestConfirmation: (confirmation: ConfirmationRequest | null) => void;
}) {
  const [text, setText] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const trackerStages = ["pending", "preparing", "submitted", "waiting", "result"];
  const tasksByStatus = useMemo(() => {
    const groups = new Map<string, ApplicationTaskRecord[]>();
    for (const task of tasks) {
      const status = formatDisplayValue(task.status || "pending").toLowerCase();
      groups.set(status, [...(groups.get(status) ?? []), task]);
    }
    return groups;
  }, [tasks]);
  const taskKey = (task: ApplicationTaskRecord) => task.internal_id || task.id;
  const moveTask = (task: ApplicationTaskRecord, stage: string) => {
    const currentStatus = formatDisplayValue(task.status || "pending").toLowerCase();
    if (currentStatus === stage) return;
    const taskLabel = formatDisplayValue(task.title || task.next_task);
    requestConfirmation({
      title: "Move tracker card?",
      detail: `"${taskLabel}" will move from ${formatDisplayValue(currentStatus)} to ${formatDisplayValue(stage)}.`,
      confirmLabel: "Move",
      cancelLabel: "Cancel",
      onConfirm: async () => {
        const taskId = taskKey(task);
        await runAction("tracker", "Moving tracker card...", async () => {
          const result = await api(`/tracker/${taskId}/status`, token, {
            method: "PATCH",
            body: JSON.stringify({ status: stage }),
          });
          setOutput(result);
          await refreshWorkspace();
        }, "Tracker card moved.");
      },
    });
  };
  return (
    <div className="atlas-page">
      <section className="atlas-header">
        <p>Applications move through a route instead of sitting in a flat list.</p>
      </section>
      <div className="atlas-body">
        <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Application journey board</div>
              <div className="atlas-card-subtitle">Each column is a route stage. Move opportunities forward as progress happens.</div>
              {!hasOpportunities ? (
                <EmptyState
                  title="Save an opportunity to start tracking"
                  detail="Your tracker becomes useful after you save a scholarship, internship, or fellowship from search results."
                  action={<button className="atlas-btn atlas-btn-green" onClick={() => setTab("search")}><Search size={16} /> Run search</button>}
                />
              ) : (
                <div className="route-board">
                  {trackerStages.map((stage) => {
                    const stageTasks = tasksByStatus.get(stage) ?? [];
                    return (
                    <div
                      className={`route-col ${draggedTaskId ? "drop-ready" : ""}`}
                      key={stage}
                      onDragOver={(event) => {
                        if (!draggedTaskId) return;
                        event.preventDefault();
                        event.dataTransfer.dropEffect = "move";
                      }}
                      onDrop={(event) => {
                        event.preventDefault();
                        const id = event.dataTransfer.getData("text/plain") || draggedTaskId;
                        setDraggedTaskId(null);
                        const task = tasks.find((item) => taskKey(item) === id || item.id === id);
                        if (task) moveTask(task, stage);
                      }}
                    >
                      <h4>{formatDisplayValue(stage)}</h4>
                      {stageTasks.length === 0 ? (
                        <div className="route-empty">No tasks yet.</div>
                      ) : (
                        stageTasks.map((task) => (
                          <ApplicationTaskCard
                            task={task}
                            key={task.id}
                            draggable
                            onDragStart={(event) => {
                              const id = taskKey(task);
                              event.dataTransfer.setData("text/plain", id);
                              event.dataTransfer.effectAllowed = "move";
                              setDraggedTaskId(id);
                            }}
                            onDragEnd={() => setDraggedTaskId(null)}
                          />
                        ))
                      )}
                    </div>
                  )})}
                </div>
              )}
            </div>
          </div>
        <div className="atlas-layout">
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Update route</div>
              <div className="atlas-card-subtitle">Update an opportunity without leaving the tracker.</div>
              <div className="atlas-grid2">
                <OpportunityIdField label="Opportunity ID" value={opportunityId} onChange={setOpportunityId} options={opportunityOptions} />
                <label><span className="atlas-label">New status</span><select className="atlas-input" value={text} onChange={(event) => setText(event.target.value)}><option value="">Preparing</option><option>Submitted</option><option>Waiting</option><option>Interview</option><option>Result</option></select></label>
              </div>
              <label className="atlas-field-space"><span className="atlas-label">Update note</span><textarea className="atlas-input" value={text} onChange={(event) => setText(event.target.value)} placeholder="Added SOP draft, waiting for transcript upload" /></label>
              <div className="atlas-actions">
                <button className="atlas-btn atlas-btn-green" onClick={async () => runAction("tracker", "Updating tracker...", async () => {
                  setOutput(await api("/tracker/update", token, { method: "POST", body: JSON.stringify({ text, opportunity_id: opportunityId || null }) }));
                  await refreshWorkspace();
                }, "Tracker updated successfully.")} disabled={!text || loading.tracker}>{loading.tracker ? <Spinner /> : <CalendarClock size={16} />} Update tracker</button>
                <button className="atlas-btn atlas-btn-dark" onClick={async () => runAction("tracker", "Loading tracker...", async () => {
                  const result = await api("/tracker", token);
                  setOutput(result);
                  await refreshWorkspace();
                }, "Tracker loaded successfully.")} disabled={loading.tracker}>Load tracker</button>
              </div>
            </div>
          </div>
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Next actions</div>
              {!hasOpportunities ? (
                <div className="template-mini-note">Save an opportunity first, then Compass can help turn it into deadlines, documents, and reminders.</div>
              ) : tasks.length > 0 ? (
                <div className="atlas-stack">
                  {tasks.slice(0, 6).map((task) => (
                    <ApplicationTaskCard task={task} variant="compact" key={task.id} />
                  ))}
                </div>
              ) : (
                <div className="template-mini-note">Open an opportunity with a listed deadline and click Plan to create tracked tasks.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ApplicationTaskCard({
  task,
  variant = "board",
  draggable = false,
  onDragStart,
  onDragEnd,
}: {
  task: ApplicationTaskRecord;
  variant?: "board" | "compact";
  draggable?: boolean;
  onDragStart?: (event: React.DragEvent<HTMLElement>) => void;
  onDragEnd?: () => void;
}) {
  const dueLabel = task.due_date ? formatDeadline(task.due_date) : "No due date";
  const opportunityLabel = task.opportunity?.title || task.opportunity_id;
  const taskCode = task.task_code || task.id;
  const emailSent = Boolean(task.email_status?.sent);
  return (
    <article
      className={`app-item ${variant === "compact" ? "app-item-compact" : ""} ${draggable ? "draggable" : ""}`.trim()}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <div className="app-item-topline">
        <strong>{formatDisplayValue(task.title || task.next_task)}</strong>
        <span className={`task-status-pill ${emailSent ? "sent" : ""}`}>{emailSent ? "Sent" : "No email"}</span>
      </div>
      <div className="task-meta-grid">
        <span><b>ID</b>{formatDisplayValue(taskCode)}</span>
        <span><b>Opportunity</b>{formatDisplayValue(opportunityLabel)}</span>
        <span><b>Due</b>{dueLabel}</span>
      </div>
      {task.notes && <p>{task.notes}</p>}
    </article>
  );
}

function DocumentPanel({ token, profile, setOutput, runAction, loading, opportunityOptions }: PanelProps & { profile: StudentProfile | null; opportunityOptions: OpportunityRecord[] }) {
  const [opportunityId, setOpportunityId] = useState("");
  const [documentType, setDocumentType] = useState("sop");
  const [documentTone, setDocumentTone] = useState("professional");
  const [documentNotes, setDocumentNotes] = useState("");
  const [cvText, setCvText] = useState("");
  const [uploads, setUploads] = useState<UploadedFileRecord[]>([]);
  const [selectedUploadId, setSelectedUploadId] = useState("");
  const [documents, setDocuments] = useState<GeneratedDocumentRecord[]>([]);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [regenerationInstructions, setRegenerationInstructions] = useState<Record<string, string>>({});
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [draftViewOpen, setDraftViewOpen] = useState(false);

  const selectedUpload = uploads.find((upload) => upload.id === selectedUploadId);
  const selectedUploadName = selectedUpload?.original_filename ?? selectedUpload?.path?.split("/").pop() ?? selectedUpload?.id ?? "";
  const draftInstruction = [
    documentTone ? `Use a ${documentTone} tone.` : null,
    documentNotes ? `User notes: ${documentNotes}` : null,
  ].filter(Boolean).join(" ");
  const cvInput = selectedUpload ? null : [cvText, documentNotes ? `Draft notes: ${documentNotes}` : ""].filter(Boolean).join("\n\n") || null;
  const usableUploads = uploads.filter((row) => row.extracted_text);
  const documentGroups = useMemo(() => groupDocumentVersions(documents), [documents]);
  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? documentGroups[0]?.versions[0] ?? null;
  const selectedGroup = selectedDocument ? documentGroups.find((group) => group.rootId === documentRootId(selectedDocument)) : null;
  const draftPreviewText = (selectedDocument ? draftEdits[selectedDocument.id] ?? selectedDocument.content ?? "" : "").trim();
  const previewLines = useMemo(() => {
    const lines = draftPreviewText
      .split(/\r?\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length) return lines.slice(0, 10);
    return [];
  }, [draftPreviewText]);
  const loadUploads = async (silent = false) => {
    const result = await api("/uploads?limit=25", token);
    const rows = (result.uploads ?? []) as UploadedFileRecord[];
    const extractedRows = rows.filter((row) => row.extracted_text);
    setUploads(extractedRows);
    setSelectedUploadId((current) => current || bestDocumentUpload(extractedRows)?.id || "");
    setOutput(result);
  };
  useEffect(() => {
    let cancelled = false;
    if (!token) return;
    (async () => {
      try {
        const result = await api("/uploads?limit=25", token);
        if (cancelled) return;
        const rows = ((result.uploads ?? []) as UploadedFileRecord[]).filter((row) => row.extracted_text);
        setUploads(rows);
        setSelectedUploadId((current) => current || bestDocumentUpload(rows)?.id || "");
      } catch {
        if (!cancelled) setUploads([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);
  const loadDocuments = async () => runAction("documents", "Loading generated documents...", async () => {
    const result = await api("/documents", token);
    const rows = (result.documents ?? []) as GeneratedDocumentRecord[];
    setDocuments(rows);
    setSelectedDocumentId((current) => current || rows[0]?.id || "");
    setOutput(result);
  }, "Documents loaded successfully.");
  const generate = async (parent?: GeneratedDocumentRecord) => runAction("documents", parent ? "Regenerating a new document version..." : "Generating a grounded draft and checking claims...", async () => {
    const result = await api("/documents/generate", token, {
      method: "POST",
      body: JSON.stringify({
        opportunity_id: opportunityId,
        document_type: parent?.document_type ?? documentType,
        profile: profile ?? {},
        cv_text: cvInput,
        uploaded_file_id: selectedUpload?.id ?? null,
        regeneration_instruction: parent ? regenerationInstructions[parent.id] || null : draftInstruction || null,
        parent_document_id: parent?.parent_document_id ?? parent?.id ?? null,
      }),
    });
    setDocuments((current) => [result.document, ...current.filter((item) => item.id !== result.document.id)]);
    setDraftEdits((current) => ({ ...current, [result.document.id]: result.document.content ?? "" }));
    setSelectedDocumentId(result.document.id);
    if (parent) setRegenerationInstructions((current) => ({ ...current, [parent.id]: "" }));
    setOutput(result);
  }, parent ? "New document version generated successfully." : "Document generated successfully.");
  const saveEditedDocument = async (document: GeneratedDocumentRecord) => runAction("documents", "Saving edited draft...", async () => {
    const content = draftEdits[document.id] ?? document.content ?? "";
    const result = await api(`/documents/${document.id}`, token, { method: "PATCH", body: JSON.stringify({ content }) });
    setDocuments((current) => current.map((item) => (item.id === document.id ? result.document : item)));
    setDraftEdits((current) => ({ ...current, [result.document.id]: result.document.content ?? "" }));
    setOutput(result);
  }, "Draft edits saved successfully.");
  const downloadDocument = (document: GeneratedDocumentRecord) => {
    const blob = new Blob([draftEdits[document.id] ?? document.content ?? ""], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${document.document_type ?? "document"}-${document.id}.txt`;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const downloadDocumentFile = async (document: GeneratedDocumentRecord, format: "txt" | "docx") => {
    const response = await fetch(`${API_URL}/documents/${document.id}/download?format=${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Download failed (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${document.document_type ?? "document"}-${document.id}.${format}`;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="atlas-page">
      <section className="atlas-header">
        <p>Generate grounded drafts while the system checks quality, relevance, and missing context.</p>
      </section>

      <div className="atlas-body">
        <div className="atlas-layout-3">
          <div className="atlas-card document-generate-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Generate document</div>
              <div className="atlas-card-subtitle">Use profile data, uploaded files, and opportunity details.</div>
              <OpportunityIdField label="Opportunity ID" value={opportunityId} onChange={setOpportunityId} options={opportunityOptions} />
              <div className="atlas-grid2 atlas-field-space">
                <label><span className="atlas-label">Document type</span><select className="atlas-input" value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
                <option value="sop">Statement of Purpose</option>
                <option value="cover_letter">Cover Letter</option>
                <option value="professor_email">Professor Email</option>
                <option value="motivation_letter">Motivation Letter</option>
                <option value="recommendation_letter">Recommendation Letter</option>
                <option value="cv_review">CV Improvement</option>
              </select></label>
                <label><span className="atlas-label">Tone</span><select className="atlas-input" value={documentTone} onChange={(event) => setDocumentTone(event.target.value)}>
                <option value="professional">Professional</option>
                <option value="confident">Confident</option>
                <option value="academic">Academic</option>
                <option value="concise">Concise</option>
                <option value="warm">Warm</option>
              </select></label>
              </div>
              <label className="atlas-field-space"><span className="atlas-label">Use uploaded file</span><select className="atlas-input" value={selectedUploadId} onChange={(event) => setSelectedUploadId(event.target.value)}>
                <option value="">Manual text override</option>
                {usableUploads.map((upload) => (
                  <option value={upload.id} key={upload.id}>{uploadPurposeLabel(upload)} · {upload.original_filename ?? upload.path?.split("/").pop() ?? upload.id}</option>
                ))}
              </select></label>
          {selectedUpload ? (
            <div className="upload-context upload-context-compact">
              <div>
                <strong>Using uploaded document</strong>
                <span>{uploadPurposeLabel(selectedUpload)} · {selectedUploadName}</span>
              </div>
              <p>{(selectedUpload.extracted_text ?? "").slice(0, 220)}{(selectedUpload.extracted_text?.length ?? 0) > 220 ? "..." : ""}</p>
            </div>
          ) : (
            <label className="atlas-field-space"><span className="atlas-label">Profile or CV context</span><textarea className="atlas-input" value={cvText} onChange={(event) => setCvText(event.target.value)} placeholder="Paste CV, transcript, achievements, or relevant background text here." /></label>
          )}
          <label className="atlas-field-space"><span className="atlas-label">Notes</span><textarea className="atlas-input" value={documentNotes} onChange={(event) => setDocumentNotes(event.target.value)} placeholder="Mention AI projects, strong academic record, and interest in research." /></label>
          <div className="atlas-actions">
            <button className="atlas-btn atlas-btn-green" onClick={() => generate()} disabled={!opportunityId || loading.documents}>{loading.documents ? <Spinner /> : <FileText size={16} />} {loading.documents ? "Generating..." : "Generate draft"}</button>
            <button className="atlas-btn atlas-btn-dark" onClick={async () => runAction("documents", "Loading uploaded CVs and transcripts...", async () => loadUploads(), "Uploads loaded successfully.")} disabled={loading.documents}><Upload size={16} /> Refresh uploads</button>
            <button className="atlas-btn atlas-btn-dark" onClick={loadDocuments} disabled={loading.documents}>Load documents</button>
          </div>
          {loading.documents && <LoadingNote title="Drafting carefully" detail="Compass is writing from your profile, opportunity data, uploaded files, and notes, then running a grounding check." />}
            </div>
        </div>

          <motion.button
            className="atlas-card draft-preview-card"
            type="button"
            layoutId="draft-preview-card"
            onClick={() => selectedDocument && setDraftViewOpen(true)}
            disabled={!selectedDocument}
            whileHover={{ scale: selectedDocument ? 1.01 : 1 }}
            whileTap={{ scale: selectedDocument ? 0.99 : 1 }}
          >
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Draft preview</div>
              <div className="atlas-card-subtitle draft-preview-subtitle">
                <span>Preview the generated draft here.</span>
                <span>Click the preview to view and edit the full document.</span>
              </div>
              <div className="doc-stage">
                <div className="paper">
                  <h3>{documentType === "sop" ? "SOP Draft" : documentType === "cv_review" ? "CV Review" : documentType === "recommendation_letter" ? "Recommendation" : "Draft"}</h3>
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={selectedDocument?.id || documentType}
                      className="paper-content"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.28, ease: "easeOut" }}
                    >
                      {previewLines.map((line, index) => (
                        <motion.p
                          className={`paper-line-text ${index === 0 ? "lead" : ""}`}
                          key={`${selectedDocument?.id || documentType}-${index}-${line.slice(0, 24)}`}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.24, delay: index * 0.05 }}
                        >
                          {line}
                        </motion.p>
                      ))}
                    </motion.div>
                  </AnimatePresence>
                </div>
              </div>
            </div>
          </motion.button>

          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Draft quality</div>
              <div className="atlas-card-subtitle">Compass checks whether the draft is usable before submission.</div>
              <div className="atlas-status-row"><b>Profile grounded</b><span>{profile ? "Yes" : "No"}</span></div>
              <div className="atlas-status-row"><b>Opportunity specific</b><span>{opportunityId ? "Yes" : "No"}</span></div>
              <div className="atlas-status-row"><b>Context available</b><span>{selectedUpload || cvText ? "Yes" : "No"}</span></div>
              <div className="atlas-status-row"><b>Word count safe</b><span>Yes</span></div>
              <div className="atlas-status-row"><b>Needs human review</b><span>Yes</span></div>
            </div>
          </div>
        </div>
      <AnimatePresence mode="wait" initial={false}>
        {draftViewOpen && documents.length > 0 && selectedDocument && (
          <motion.div
            className="document-review-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setDraftViewOpen(false)}
          >
            <motion.div
              className="document-review-layout"
              layoutId="draft-preview-card"
              transition={{ type: "spring", stiffness: 120, damping: 18 }}
              onClick={(event) => event.stopPropagation()}
            >
              <aside className="version-history">
                <PanelHeader title="Version history" meta={`${documents.length} saved draft${documents.length === 1 ? "" : "s"}`} />
                {documentGroups.map((group) => (
                  <section key={group.rootId}>
                    <strong>{formatDisplayValue(group.versions[0]?.document_type)}</strong>
                    {group.versions.map((document) => (
                      <button
                        key={document.id}
                        className={document.id === selectedDocument.id ? "active" : ""}
                        onClick={() => setSelectedDocumentId(document.id)}
                      >
                        <span>Version {document.version_number ?? 1}</span>
                        <small>{document.updated_at || document.created_at ? formatDeadline(document.updated_at ?? document.created_at) : "Saved draft"}</small>
                      </button>
                    ))}
                  </section>
                ))}
              </aside>

              <article className="document-card focused">
                <div className="document-card-topline">
                  <div>
                    <strong>{formatDisplayValue(selectedDocument.document_type)}</strong>
                    <small>
                      Version {selectedDocument.version_number ?? 1}
                      {selectedGroup ? ` of ${selectedGroup.versions.length}` : ""}
                    </small>
                  </div>
                  <div className="button-row compact">
                    <button onClick={() => setDraftViewOpen(false)}>Back</button>
                    <button onClick={() => saveEditedDocument(selectedDocument)} disabled={loading.documents}>Save</button>
                    <button onClick={() => downloadDocument(selectedDocument)}>Download txt</button>
                    <button
                      onClick={() => runAction("documents", "Preparing DOCX download...", async () => {
                        await downloadDocumentFile(selectedDocument, "docx");
                      }, "DOCX download ready.")}
                      disabled={loading.documents}
                    >
                      Download docx
                    </button>
                  </div>
                </div>

                <div className="nested-draft-shell">
                  <textarea
                    className="document-editor nested"
                    value={draftEdits[selectedDocument.id] ?? selectedDocument.content ?? ""}
                    onChange={(event) => setDraftEdits((current) => ({ ...current, [selectedDocument.id]: event.target.value }))}
                  />

                  {selectedDocument.regeneration_instruction && (
                    <div className="review-note">
                      <strong>Previous instruction</strong>
                      <span>{selectedDocument.regeneration_instruction}</span>
                    </div>
                  )}

                  {selectedDocument.grounding_flags?.length ? (
                    <div className="review-flags">
                      <strong>Grounding review</strong>
                      {selectedDocument.grounding_flags.map((flag) => <span key={flag}>{flag}</span>)}
                    </div>
                  ) : (
                    <div className="review-ok">
                      <CheckCircle2 size={17} />
                      <span>Grounding check did not return unsupported-claim flags.</span>
                    </div>
                  )}

                  <label>
                    AI rewrite instruction
                    <input
                      value={regenerationInstructions[selectedDocument.id] ?? ""}
                      onChange={(event) => setRegenerationInstructions((current) => ({ ...current, [selectedDocument.id]: event.target.value }))}
                      placeholder="e.g. make it more concise and emphasize research experience"
                    />
                  </label>
                  <div className="button-row">
                    <button onClick={() => generate(selectedDocument)} disabled={!opportunityId || loading.documents}>
                      {loading.documents ? <Spinner /> : <FileText size={16} />} Rewrite as new version
                    </button>
                  </div>
                </div>
              </article>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </div>
  );
}

function UploadPanel({
  token,
  setOutput,
  runAction,
  loading,
  uploads,
  refreshWorkspace,
}: PanelProps & {
  uploads: UploadedFileRecord[];
  refreshWorkspace: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState("cv");
  const fileLabel = useMemo(() => file?.name ?? "No file selected", [file]);
  const latestUpload = uploads[0];
  const extractedCount = uploads.filter((upload) => upload.extracted_text || upload.extracted_json).length;
  const upload = async (path: string) => {
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    if (path.includes("document")) form.set("purpose", purpose);
    const key = path.includes("poster") ? "uploadPoster" : "uploadDocument";
    await runAction(key, path.includes("poster") ? "Uploading poster and extracting visual details..." : "Uploading document and extracting text/OCR...", async () => {
      setOutput(await api(path, token, { method: "POST", body: form }));
      await refreshWorkspace();
    }, path.includes("poster") ? "Poster uploaded successfully." : "Document uploaded successfully.");
  };
  return (
    <div className="atlas-page">
      <section className="atlas-header">
        <p>Upload files and let Compass extract useful signals for matching and document generation.</p>
      </section>
      <div className="atlas-body">
        <div className="atlas-layout">
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Upload gateway</div>
              <div className="atlas-card-subtitle">Upload a CV, transcript, or document. Text will be extracted to support search and document generation.</div>
              <label className="upload-gate">
                <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                <div className="upload-gate-scan" />
                <div className="upload-content">
                  <Upload size={32} />
                  <b>{fileLabel === "No file selected" ? "Drop a file here or browse" : fileLabel}</b>
                  <span>PDF, DOCX, PNG, JPG up to 20 MB</span>
                </div>
              </label>
              <div className="atlas-grid2 atlas-field-space">
                <label><span className="atlas-label">Document purpose</span><select className="atlas-input" value={purpose} onChange={(event) => setPurpose(event.target.value)}><option value="cv">CV or resume</option><option value="transcript">Transcript</option><option value="poster">Scholarship poster</option><option value="research_statement">Research statement</option></select></label>
                <label><span className="atlas-label">Processing mode</span><select className="atlas-input"><option>Extract profile signals</option><option>Read opportunity poster</option><option>Store only</option></select></label>
              </div>
              <div className="atlas-actions">
                <button className="atlas-btn atlas-btn-green" onClick={() => upload("/upload/document")} disabled={!file || loading.uploadDocument}>{loading.uploadDocument ? <Spinner /> : <Upload size={16} />} Upload document</button>
                <button className="atlas-btn atlas-btn-dark" onClick={() => upload("/upload/poster")} disabled={!file || loading.uploadPoster}>{loading.uploadPoster ? <Spinner /> : <FileText size={16} />} Upload poster</button>
              </div>
              {(loading.uploadPoster || loading.uploadDocument) && <LoadingNote title="Processing upload" detail="OCR or vision extraction may take longer for scanned PDFs and large images." />}
            </div>
          </div>
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">File processing</div>
              <div className="atlas-card-subtitle">Extraction results will appear here after upload.</div>
              <div className="atlas-status-row"><b>OCR status</b><span>{loading.uploadDocument || loading.uploadPoster ? "Processing" : "Ready"}</span></div>
              <div className="atlas-status-row"><b>Extracted files</b><span>{extractedCount}</span></div>
              <div className="atlas-status-row"><b>Files in vault</b><span>{uploads.length}</span></div>
              <div className="atlas-status-row"><b>Latest upload</b><span>{latestUpload?.path?.split("/").pop() ?? (fileLabel === "No file selected" ? "Waiting" : fileLabel)}</span></div>
            </div>
          </div>
        </div>
        <div className="atlas-card">
          <div className="atlas-card-inner">
            <div className="atlas-card-title">Document library</div>
            <div className="atlas-card-subtitle">A structured vault for all uploaded files.</div>
            {uploads.length === 0 && !file && (
              <EmptyState
                title="Upload your CV"
                detail="A CV or resume helps Compass understand your experience, skills, and application context before matching."
                action={<button className="atlas-btn atlas-btn-green" onClick={() => setPurpose("cv")}><Upload size={16} /> Choose CV above</button>}
              />
            )}
            {(uploads.length > 0 || file) && (
              <div className="table-wrap atlas-table-wrap">
                <table className="table">
                  <thead><tr><th>File</th><th>Purpose</th><th>Type</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {file && (
                      <tr><td><b>{file.name}</b></td><td>{purpose}</td><td>{file.type || "Unknown"}</td><td>Ready to upload</td><td>Upload</td></tr>
                    )}
                    {uploads.map((upload) => (
                      <tr key={upload.id}>
                        <td><b>{upload.path?.split("/").pop() ?? upload.id}</b></td>
                        <td>{uploadPurposeLabel(upload)}</td>
                        <td>{upload.mime_type || "Unknown"}</td>
                        <td>{upload.extracted_text || upload.extracted_json ? "Extracted" : "Stored"}</td>
                        <td>{upload.created_at ? formatDeadline(upload.created_at) : "Saved"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function NotificationPanel({
  token,
  setOutput,
  runAction,
  loading,
  tasks,
}: PanelProps & {
  tasks: ApplicationTaskRecord[];
}) {
  const [notificationEmail, setNotificationEmail] = useState("");
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [reminderDays, setReminderDays] = useState("15,7,3,1,0");
  const reminderDayValues = reminderDays
    .split(",")
    .map((day) => Number(day.trim()))
    .filter((day) => Number.isFinite(day) && day >= 0);
  const todayTime = new Date().setHours(0, 0, 0, 0);
  const taskUrgency = tasks.reduce(
    (summary, task) => {
      if (!task.due_date) {
        summary.noDate += 1;
        return summary;
      }
      const dueTime = new Date(task.due_date).setHours(0, 0, 0, 0);
      const daysUntilDue = Math.ceil((dueTime - todayTime) / 86_400_000);
      if (daysUntilDue <= 7) summary.high += 1;
      else summary.normal += 1;
      return summary;
    },
    { high: 0, normal: 0, noDate: 0 },
  );
  const upcomingTasks = [...tasks]
    .filter((task) => task.due_date)
    .sort((a, b) => new Date(a.due_date || 0).getTime() - new Date(b.due_date || 0).getTime())
    .slice(0, 5);
  const toggleReminderDay = (day: number) => {
    const next = reminderDayValues.includes(day) ? reminderDayValues.filter((item) => item !== day) : [...reminderDayValues, day];
    setReminderDays(next.sort((a, b) => b - a).join(","));
  };
  const loadPreferences = async () => {
    const result = await api("/notifications/preferences", token);
    const preferences = result.preferences ?? {};
    setOutput(result);
    setNotificationEmail(preferences.notification_email ?? "");
    setEmailEnabled(preferences.email_enabled ?? true);
    setReminderDays((preferences.reminder_days ?? [15, 7, 3, 1, 0]).join(","));
  };
  return (
    <div className="atlas-page">
      <section className="atlas-header">
        <p>Reminder settings are shown with deadline intelligence so urgency is easy to understand.</p>
      </section>
      <div className="atlas-body">
        <div className="atlas-layout">
          <div className="atlas-stack">
            <div className="atlas-card">
              <div className="atlas-card-inner">
                <div className="atlas-card-title">Reminder settings</div>
                <div className="atlas-card-subtitle">Choose where and when deadline reminders should be sent.</div>
                <div className="atlas-grid2">
                  <label><span className="atlas-label">Email address</span><input className="atlas-input" value={notificationEmail} onChange={(event) => setNotificationEmail(event.target.value)} placeholder="your@email.com" /></label>
                  <label><span className="atlas-label">Days before deadline</span><input className="atlas-input" value={reminderDays} onChange={(event) => setReminderDays(event.target.value)} placeholder="15, 7, 3, 1, 0" /></label>
                </div>
                <div className="reminder-chip-grid">
                  {[15, 7, 3, 1, 0].map((day) => (
                    <button type="button" key={day} className={`reminder-chip ${reminderDayValues.includes(day) ? "active" : ""}`} onClick={() => toggleReminderDay(day)}>
                      <b>{day}</b><span>{day === 0 ? "due day" : day === 1 ? "day" : "days"}</span>
                    </button>
                  ))}
                </div>
                <label className="check-row atlas-check"><input type="checkbox" checked={emailEnabled} onChange={(event) => setEmailEnabled(event.target.checked)} /> Email reminders enabled</label>
                <div className="atlas-actions">
                  <button className="atlas-btn atlas-btn-green" onClick={async () => runAction("notifications", "Saving reminder preferences...", async () => setOutput(await api("/notifications/preferences", token, { method: "POST", body: JSON.stringify({ notification_email: notificationEmail || null, email_enabled: emailEnabled, reminder_days: reminderDayValues }) })), "Notification preferences saved successfully.")} disabled={loading.notifications}>{loading.notifications ? <Spinner /> : <Mail size={16} />} Save preferences</button>
                  <button className="atlas-btn atlas-btn-dark" onClick={async () => runAction("notifications", "Loading reminder preferences...", loadPreferences, "Tracker reminder preferences loaded.")} disabled={loading.notifications}>Load</button>
                </div>
              </div>
            </div>
            <div className="atlas-card">
              <div className="atlas-card-inner">
                <div className="atlas-card-title">Reminder schedule preview</div>
                {[15, 7, 3, 1, 0].map((day) => <div className="atlas-status-row" key={day}><b>{reminderDayLabel(day)}</b><span>{reminderDayValues.includes(day) && emailEnabled ? "Enabled" : "Off"}</span></div>)}
              </div>
            </div>
          </div>
          <div className="atlas-card">
            <div className="atlas-card-inner">
              <div className="atlas-card-title">Deadline radar</div>
              <div className="atlas-card-subtitle">Urgency summary across all tracked applications based on their deadlines.</div>
              <div className="deadline-summary">
                <div><b>{taskUrgency.high}</b><span>High attention</span></div>
                <div><b>{taskUrgency.normal}</b><span>Normal</span></div>
                <div><b>{taskUrgency.noDate}</b><span>No due date</span></div>
              </div>
              {upcomingTasks.length === 0 ? (
                <div className="template-mini-note">Create a deadline plan from an opportunity with a listed deadline to see reminder targets here.</div>
              ) : (
                upcomingTasks.map((task) => (
                  <div className="atlas-status-row" key={task.id}>
                    <b>{formatDisplayValue(task.title || task.next_task)}</b>
                    <span>{formatDisplayValue(task.task_code || task.id)} · {formatDeadline(task.due_date)} · {emailStatusLabel(task)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminPanel({ token, setOutput, runAction, loading }: PanelProps) {
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [evalRuns, setEvalRuns] = useState<EvalRunRecord[]>([]);
  const loadHealth = async () => runAction("admin", "Loading system health...", async () => {
    const result = await api<{ health: AdminHealth }>("/admin/health", token);
    setHealth(result.health);
    setOutput(result);
  }, "Health console loaded successfully.");
  const loadEvalRuns = async () => runAction("admin", "Loading eval runs...", async () => {
    const result = await api<{ eval_runs?: EvalRunRecord[] }>("/admin/eval-runs", token);
    setEvalRuns((result.eval_runs ?? []) as EvalRunRecord[]);
    setOutput(result);
  }, "Eval runs loaded successfully.");
  const latestEvalRun = evalRuns[0] ?? null;

  return (
    <div className="panel-stack">
      <div className="panel">
        <PanelHeader title="System health" meta="Jobs, providers, and recent API calls" action={<button onClick={loadHealth} disabled={loading.admin}>{loading.admin ? <Spinner /> : <Activity size={16} />} Refresh</button>} />
        {health ? (
          <div className="health-grid">
            {Object.entries(health.providers || {}).map(([provider, stats]) => (
              <div className="metric-card" key={provider}>
                <span>{provider}</span>
                <strong>{stats.calls ?? 0} calls</strong>
                <small>{stats.failures ?? 0} failures · {stats.avg_latency_ms ?? 0} ms avg</small>
              </div>
            ))}
            {!Object.keys(health.providers || {}).length && <p className="muted-text">No API calls logged yet.</p>}
          </div>
        ) : (
          <p className="muted-text">Refresh to load provider health and recent search jobs.</p>
        )}
        {health?.recent_jobs?.length ? (
          <div className="job-list">
            {health.recent_jobs.slice(0, 6).map((job) => (
              <div key={job.id}>
                <strong>{job.status}</strong>
                <span>{job.progress_message || job.error || job.id}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div className="panel">
        <PanelHeader title="Eval report" meta="Latest saved extraction run" action={<button onClick={loadEvalRuns} disabled={loading.admin}>{loading.admin ? <Spinner /> : <FileText size={16} />} Refresh</button>} />
        {latestEvalRun ? (
          <div className="health-grid">
            <div className="metric-card">
              <span>Model</span>
              <strong>{latestEvalRun.model_name ?? "Unknown"}</strong>
              <small>{latestEvalRun.created_at ? new Date(latestEvalRun.created_at).toLocaleString() : "Recent"}</small>
            </div>
            <div className="metric-card">
              <span>Extraction accuracy</span>
              <strong>{latestEvalRun.extraction_accuracy != null ? `${Math.round(latestEvalRun.extraction_accuracy * 1000) / 10}%` : "N/A"}</strong>
              <small>Golden-set average</small>
            </div>
            <div className="metric-card">
              <span>Hallucination rate</span>
              <strong>{latestEvalRun.hallucination_rate != null ? `${Math.round(latestEvalRun.hallucination_rate * 1000) / 10}%` : "N/A"}</strong>
              <small>Cases with unsupported fields</small>
            </div>
          </div>
        ) : (
          <p className="muted-text">Run evals to generate and save the latest report here.</p>
        )}
        {latestEvalRun?.notes && <p className="muted-text">{latestEvalRun.notes}</p>}
      </div>
      <div className="panel">
        <PanelHeader title="Review tools" meta="Evaluation and source trust inspection" />
        <div className="admin-actions">
          <button onClick={async () => runAction("admin", "Running eval suite and saving the summary...", async () => setOutput(await api("/admin/run-eval", token, { method: "POST", body: "{}" })), "Eval suite completed and saved successfully.")} disabled={loading.admin}><Activity size={16} /> Run evals</button>
          <button onClick={loadEvalRuns} disabled={loading.admin}><FileText size={16} /> Eval runs</button>
          <button onClick={async () => runAction("admin", "Loading source flags...", async () => setOutput(await api("/admin/source-flags", token)), "Source flags loaded successfully.")} disabled={loading.admin}><ShieldAlert size={16} /> Source flags</button>
          <button onClick={async () => runAction("admin", "Checking OCR status...", async () => setOutput(await api("/health/ocr", token)), "OCR status checked successfully.")} disabled={loading.admin}><Settings size={16} /> OCR health</button>
        </div>
      </div>
    </div>
  );
}

type PanelProps = {
  token: string;
  setOutput: (value: unknown) => void;
  runAction: (key: LoadingKey, message: string, action: () => Promise<void>, successMessage?: string) => Promise<void>;
  loading: Partial<Record<LoadingKey, boolean>>;
};

function PanelHeader({ title, meta, action }: { title: string; meta?: string; action?: React.ReactNode }) {
  return (
    <div className="panel-header">
      <div>
        <h3>{title}</h3>
        {meta && <span>{meta}</span>}
      </div>
      {action}
    </div>
  );
}

function InsightPanel({
  tab,
  profileComplete,
  searchJob,
  searchSummary,
  savedOpportunities,
  documents,
  uploads,
}: {
  tab: Tab;
  profileComplete: boolean;
  searchJob: SearchJob | null;
  searchSummary: SearchResultPayload | null;
  savedOpportunities: OpportunityRecord[];
  documents: GeneratedDocumentRecord[];
  uploads: UploadedFileRecord[];
}) {
  const activeSearch = searchJob && ["queued", "running"].includes(searchJob.status);
  const searchCount = searchSummary?.opportunities?.length ?? searchJob?.result?.opportunities?.length ?? 0;

  return (
    <aside className="result-panel insight-panel">
      <div className="panel-header">
        <div>
          <h3>Workspace insights</h3>
          <span>{pageMeta[tab].title}</span>
        </div>
      </div>
      <div className="insight-list">
        <section>
          <span>Profile readiness</span>
          <strong>{profileComplete ? "Ready for matching" : "Needs required fields"}</strong>
          <p>{profileComplete ? "Searches can use your student background." : "Add country, degree, and field to improve results."}</p>
        </section>
        <section>
          <span>Search status</span>
          <strong>{activeSearch ? searchJob?.status : searchJob?.status || "Idle"}</strong>
          <p>{searchJob?.progress_message || (searchCount ? `${searchCount} opportunities in the latest result.` : "Run a search to populate verified opportunities.")}</p>
        </section>
        <section>
          <span>Saved opportunities</span>
          <strong>{savedOpportunities.length}</strong>
          <p>{savedOpportunities[0]?.title || "Saved items will appear here after search."}</p>
        </section>
        <section>
          <span>Documents and uploads</span>
          <strong>{documents.length} drafts · {uploads.length} uploads</strong>
          <p>{documents[0]?.document_type || uploads[0]?.purpose || "Upload a CV or generate a draft to continue."}</p>
        </section>
      </div>
      {searchSummary?.errors?.length ? (
        <div className="insight-warning">
          <strong>Pipeline notes</strong>
          <span>{searchSummary.errors.slice(0, 2).join(" ")}</span>
        </div>
      ) : null}
    </aside>
  );
}

function BusyBanner({ message }: { message: string }) {
  return (
    <div className="busy-banner">
      <Spinner />
      <span>{message}</span>
    </div>
  );
}

function SidebarBrandLockup({ collapsed }: { collapsed: boolean }) {
  return (
    <div className={`sidebar-brand ${collapsed ? "sidebar-brand-collapsed" : ""}`} aria-label="Compass">
      <div className="brand-compass" aria-hidden="true">
        <span className="brand-compass-ring" />
        <span className="brand-compass-needle" />
        <span className="brand-compass-dot" />
      </div>
      {!collapsed && (
        <div className="brand-copy">
          <span className="sidebar-brand-name">Compass</span>
        </div>
      )}
    </div>
  );
}

function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-block" aria-label="Loading content">
      {Array.from({ length: lines }).map((_, index) => (
        <span key={index} className={index === 0 ? "wide" : index % 3 === 0 ? "short" : ""} />
      ))}
    </div>
  );
}

function EmptyState({ title, detail, action }: { title: string; detail: string; action?: React.ReactNode }) {
  return (
    <motion.div className="empty-state" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
      <div>
        <h3>{title}</h3>
        <p>{detail}</p>
      </div>
      {action}
    </motion.div>
  );
}

function LoadingNote({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="loading-note">
      <Spinner />
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </div>
  );
}

function NotificationBar({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  if (!notice) return null;
  const title = notice.kind === "success" ? "Compass update" : "Compass needs attention";
  const detail = notice.message === "Signed in successfully." ? "Your Compass workspace is ready." : notice.message;
  return (
    <div className={`compass-toast show ${notice.kind}`} role="status" aria-live="polite">
      <div className="toast-glow" />
      <div className="toast-icon">
        <span>{notice.kind === "success" ? "✓" : "!"}</span>
      </div>
      <div className="toast-content">
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
      <button className="toast-close" onClick={onClose} aria-label="Dismiss notification">
        ×
      </button>
      <div className="toast-progress" />
    </div>
  );
}

function ConfirmationToast({ confirmation, onClose }: { confirmation: ConfirmationRequest | null; onClose: () => void }) {
  if (!confirmation) return null;
  const confirm = async () => {
    await confirmation.onConfirm();
    onClose();
  };
  return (
    <div className="compass-toast compass-confirm show" role="alertdialog" aria-live="assertive">
      <div className="toast-glow" />
      <div className="toast-icon">
        <span>?</span>
      </div>
      <div className="toast-content">
        <strong>{confirmation.title}</strong>
        <p>{confirmation.detail}</p>
      </div>
      <div className="toast-actions">
        <button className="toast-action ghost" onClick={onClose}>
          {confirmation.cancelLabel || "Cancel"}
        </button>
        <button className="toast-action primary" onClick={confirm}>
          {confirmation.confirmLabel || "Confirm"}
        </button>
      </div>
    </div>
  );
}

function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

createRoot(document.getElementById("root")!).render(<App />);
