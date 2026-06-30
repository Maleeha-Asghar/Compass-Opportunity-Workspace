import React, { useState } from "react";
import { Bell, BookmarkCheck, ClipboardList, FileText, Search, ShieldCheck, Upload, User, X } from "lucide-react";
import type { Tab } from "../../types";

type GuideStep = {
  title: string;
  detail: string;
  actionLabel: string;
  target: Tab;
  complete: boolean;
};

type UserGuideProps = {
  profileComplete: boolean;
  hasUploads: boolean;
  hasOpportunities: boolean;
  isAdmin?: boolean;
  setTab: (tab: Tab) => void;
};

type DetailedGuideStep = {
  title: string;
  detail: string;
  target: Tab;
  actionLabel: string;
  icon: React.ReactNode;
};

function guideSteps(profileComplete: boolean, hasUploads: boolean, hasOpportunities: boolean): GuideStep[] {
  return [
    {
      title: "Step 1: Complete your profile",
      detail: "Country, degree, field, goals, and tests help Compass filter for real eligibility.",
      actionLabel: profileComplete ? "Review profile" : "Complete profile",
      target: "account",
      complete: profileComplete,
    },
    {
      title: "Step 2: Upload your CV",
      detail: "A CV or transcript gives document context for matching, drafting, and missing-requirement checks.",
      actionLabel: hasUploads ? "View uploads" : "Upload your CV",
      target: "uploads",
      complete: hasUploads,
    },
    {
      title: "Step 3: Run your first search",
      detail: "Use your profile and documents to discover verified scholarships, internships, and fellowships.",
      actionLabel: hasOpportunities ? "View opportunities" : "Run search",
      target: hasOpportunities ? "opportunities" : "search",
      complete: hasOpportunities,
    },
  ];
}

function detailedGuideSteps(profileComplete: boolean, hasUploads: boolean, hasOpportunities: boolean, isAdmin = false): DetailedGuideStep[] {
  const steps: DetailedGuideStep[] = [
    {
      title: "1. Build your profile",
      detail: profileComplete
        ? "Review country, degree, field, funding preference, tests, skills, and target regions before each serious search."
        : "Start here. Add country, degree, field, CGPA, skills, target countries, funding needs, and test status so matching is not just keyword-based.",
      target: "account",
      actionLabel: profileComplete ? "Review profile" : "Open profile",
      icon: <User size={14} />,
    },
    {
      title: "2. Add document context",
      detail: hasUploads
        ? "Use uploaded CVs or transcripts as context for document drafting and stronger eligibility checks."
        : "Upload a CV, transcript, poster, or research statement when you want Compass to extract details for matching and drafts.",
      target: "uploads",
      actionLabel: hasUploads ? "View uploads" : "Open uploads",
      icon: <Upload size={14} />,
    },
    {
      title: "3. Search with intent",
      detail: "Write a focused query with field, country or region, funding level, degree level, nationality, and deadline year. Use Refresh to review previous jobs.",
      target: "search",
      actionLabel: "Open search",
      icon: <Search size={14} />,
    },
    {
      title: "4. Review opportunities",
      detail: hasOpportunities
        ? "Open each result, check source tier, eligibility, warnings, deadline risk, and fit before saving or planning."
        : "After a search completes, review extracted opportunities here and open details before taking action.",
      target: "opportunities",
      actionLabel: "Open opportunities",
      icon: <BookmarkCheck size={14} />,
    },
    {
      title: "5. Track applications",
      detail: "Use Tracker for next actions: saved, preparing, submitted, waiting, and result. Keep notes short and tied to an opportunity ID.",
      target: "tracker",
      actionLabel: "Open tracker",
      icon: <ClipboardList size={14} />,
    },
    {
      title: "6. Draft documents",
      detail: "Generate SOPs, cover letters, professor emails, or CV improvements only after the opportunity and profile context are ready.",
      target: "documents",
      actionLabel: "Open documents",
      icon: <FileText size={14} />,
    },
    {
      title: "7. Set reminders",
      detail: "Load notification preferences and choose reminder windows so application tasks surface before deadlines.",
      target: "notifications",
      actionLabel: "Open notifications",
      icon: <Bell size={14} />,
    },
  ];
  if (isAdmin) {
    steps.push({
      title: "8. Check system review",
      detail: "Use Review to inspect provider health, recent search jobs, OCR status, eval runs, and source trust flags.",
      target: "admin",
      actionLabel: "Open review",
      icon: <ShieldCheck size={14} />,
    });
  }
  return steps;
}

export function OnboardingGuide({ profileComplete, hasUploads, hasOpportunities, setTab }: UserGuideProps) {
  const steps = guideSteps(profileComplete, hasUploads, hasOpportunities);
  const completeCount = steps.filter((step) => step.complete).length;
  const percent = Math.round((completeCount / steps.length) * 100);

  return (
    <section className="onboarding-guide" aria-label="Compass setup guide">
      <div className="guide-topline">
        <div>
          <span className="guide-eyebrow">Getting started</span>
          <h3>Your Compass setup</h3>
        </div>
        <strong>{percent}%</strong>
      </div>
      <div className="guide-progress" aria-label={`${percent}% complete`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="guide-steps">
        {steps.map((step, index) => (
          <article className={`guide-step ${step.complete ? "complete" : ""}`} key={step.title}>
            <div className="guide-step-index">{step.complete ? "OK" : index + 1}</div>
            <div>
              <h4>{step.title}</h4>
              <p>{step.detail}</p>
              <button type="button" onClick={() => setTab(step.target)}>
                {step.target === "account" && <User size={15} />}
                {step.target === "uploads" && <Upload size={15} />}
                {step.target === "search" && <Search size={15} />}
                {step.target === "opportunities" && <FileText size={15} />}
                {step.actionLabel}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function FloatingCompassHelp({ profileComplete, hasUploads, hasOpportunities, isAdmin, setTab }: UserGuideProps) {
  const [open, setOpen] = useState(false);
  const steps = guideSteps(profileComplete, hasUploads, hasOpportunities);
  const nextStep = steps.find((step) => !step.complete) ?? steps[steps.length - 1];
  const detailedSteps = detailedGuideSteps(profileComplete, hasUploads, hasOpportunities, isAdmin);

  return (
    <div className={`floating-help ${open ? "open" : ""}`}>
      {open && (
        <div className="floating-help-card" role="dialog" aria-label="Compass help">
          <div className="floating-help-head">
            <div>
              <span>Compass guide</span>
              <strong>{nextStep.complete ? "You are ready to explore" : nextStep.title}</strong>
            </div>
            <button type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close help">
              <X size={16} />
            </button>
          </div>
          <p>{nextStep.detail}</p>
          <div className="floating-guide-next">
            <span>Next best step</span>
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                setTab(nextStep.target);
                setOpen(false);
              }}
            >
              {nextStep.actionLabel}
            </button>
          </div>
          <div className="floating-guide-list" aria-label="Detailed Compass workflow">
            {detailedSteps.map((step) => (
              <article className="floating-guide-step" key={step.title}>
                <div className="floating-guide-icon">{step.icon}</div>
                <div>
                  <h4>{step.title}</h4>
                  <p>{step.detail}</p>
                  <button
                    type="button"
                    onClick={() => {
                      setTab(step.target);
                      setOpen(false);
                    }}
                  >
                    {step.actionLabel}
                  </button>
                </div>
              </article>
            ))}
          </div>
          <button
            type="button"
            className="ghost-button floating-guide-close"
            onClick={() => {
              setOpen(false);
            }}
          >
            Close guide
          </button>
        </div>
      )}
      <button
        type="button"
        className="floating-compass-button"
        onClick={() => setOpen((current) => !current)}
        aria-label="Open Compass help"
      >
        <span className="floating-compass-ring" />
        <span className="floating-compass-needle" />
        <span className="floating-compass-dot" />
      </button>
    </div>
  );
}
