/**
 * Navigation and challenge registry. Data-driven so organizer challenges can be added without
 * touching the shell. A challenge entry is shown only with its real, documented status.
 */
export type NavItem = {
  href: string;
  label: string;
  description: string;
  icon:
    | "dashboard"
    | "projects"
    | "screening"
    | "analytics"
    | "workspace"
    | "scenarios"
    | "challenges";
};

export const NAV: NavItem[] = [
  {
    href: "/projects",
    label: "Discover",
    description: "Find projects worth a closer look",
    icon: "projects",
  },
  {
    href: "/workspace",
    label: "My Shortlist",
    description: "Understand differences and decide what to review next",
    icon: "workspace",
  },
  {
    href: "/screening",
    label: "Analyze a Project",
    description: "Explore the climate relevance of a description",
    icon: "screening",
  },
  {
    href: "/challenges",
    label: "Challenges",
    description: "BATTLEVERSE organizer challenges",
    icon: "challenges",
  },
];

export type ChallengeStatus =
  "implemented_separately" | "separate_workstream" | "integrated";

export type Challenge = {
  id: string;
  title: string;
  question: string;
  status: ChallengeStatus;
  statusText: string;
  docs: string[];
};

/**
 * Integrated challenge registry. Detailed evidence lives in the secondary showcase.
 */
export const CHALLENGES: Challenge[] = [
  {
    id: "c09",
    title: "C09: Input Protection",
    question: "How should climate screening respond to adversarial inputs?",
    status: "integrated",
    statusText:
      "Opt-in local adapter, frozen model and recorded development evaluation.",
    docs: ["docs/challenges/c09_scorecard.md"],
  },
  {
    id: "c05",
    title: "C05: Data Integrity Shield",
    question:
      "Can a training batch with 5% inverted labels be screened so suspicious records are quarantined before the model learns from them?",
    status: "integrated",
    statusText:
      "Offline quarantine gate; policy A preserved and policy B remains a candidate.",
    docs: [
      "docs/challenges/c05_problem_and_solution.md",
      "docs/challenges/c05_scorecard.md",
      "docs/challenges/c05_judge_demo.md",
    ],
  },
  {
    id: "c11", title: "C11: Availability Shield",
    question: "Can normal users continue accessing Compassio under abusive traffic?",
    status: "integrated",
    statusText: "Opt-in token buckets; original capacity evidence is fixture-backed.",
    docs: ["docs/challenges/c11_scorecard.md"],
  },
];
