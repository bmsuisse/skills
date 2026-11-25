import { createFileRoute } from "@tanstack/react-router";
export const Route = createFileRoute("/articles/$articleId")({ component: () => null });
