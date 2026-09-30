export interface NavItem {
  path: string;
  label: string;
  /** Hide the link unless the user's role has this permission (display only; the API enforces it). */
  permission?: string;
}

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Portfolio",
    items: [
      { path: "/", label: "Command Center" },
      { path: "/operations", label: "Operations Board" },
      { path: "/models", label: "Model 360" },
      { path: "/monitoring", label: "Monitoring" },
      { path: "/data-audit", label: "Data Audit" },
    ],
  },
  {
    label: "Evidence & data",
    items: [
      { path: "/documents", label: "Document Centre" },
      { path: "/imports", label: "Import Centre" },
    ],
  },
  {
    label: "Control",
    items: [
      { path: "/audit", label: "Audit Trail", permission: "audit:read" },
      { path: "/admin", label: "Admin" },
    ],
  },
];
