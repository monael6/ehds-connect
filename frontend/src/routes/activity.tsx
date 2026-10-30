import { createFileRoute } from "@tanstack/react-router";
import { AuditPage } from "@/components/audit-page";
import { pageHead } from "@/lib/page-head";
export const Route = createFileRoute("/activity")({ head: () => pageHead("Activity log", "The signed-in demo user's own attributed actions."), component: () => <AuditPage own /> });
