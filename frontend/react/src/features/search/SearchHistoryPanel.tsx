import React from "react";
import { Search, Trash2, X } from "lucide-react";
import type { SearchJob } from "../../types";

type SearchHistoryPanelProps = {
  jobs: SearchJob[];
  onRefresh: () => void;
  onRetry: (job: SearchJob) => void;
  onCancel: (job: SearchJob) => void;
  onDelete: (job: SearchJob) => void;
  loading?: boolean;
};

function formatJobTime(job: SearchJob): string {
  const value = job.completed_at || job.updated_at || job.created_at;
  if (!value) return "Recent";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Recent";
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function SearchHistoryPanel({ jobs, onRefresh, onRetry, onCancel, onDelete, loading }: SearchHistoryPanelProps) {
  return (
    <article className="panel search-history-panel">
      <div className="panel-header">
        <div>
          <h3>Search history</h3>
          <span>{jobs.length ? `${jobs.length} recent job${jobs.length === 1 ? "" : "s"}` : "No searches yet"}</span>
        </div>
        <button onClick={onRefresh} disabled={loading}>
          <Search size={16} /> {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {jobs.length === 0 ? (
        <p className="muted-text">Your completed, failed, and cancelled searches will appear here for quick review.</p>
      ) : (
        <div className="history-list">
          {jobs.map((job) => (
            <div className="history-item" key={job.id}>
              <div>
                <strong>{job.query || job.progress_message || "Opportunity search"}</strong>
                <span>
                  {job.status} · {formatJobTime(job)}
                </span>
              </div>
              <div className="button-row compact">
                {["queued", "running"].includes(job.status) && (
                  <button onClick={() => onCancel(job)} disabled={loading}>
                    <X size={16} /> Cancel
                  </button>
                )}
                {["failed", "cancelled"].includes(job.status) && (
                  <button onClick={() => onRetry(job)} disabled={loading}>
                    <Search size={16} /> Retry
                  </button>
                )}
                <button onClick={() => onDelete(job)} disabled={loading} title="Delete this history entry">
                  <Trash2 size={16} /> Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
