import { createFileRoute } from "@tanstack/react-router";
import { AuditPage } from "@/components/audit-page";
import { pageHead } from "@/lib/page-head";
export const Route = createFileRoute("/audit")({ head: () => pageHead("HDAB audit", "Filter attributed health data actions by user, role, area, patient, request and date."), component: AuditPage });
