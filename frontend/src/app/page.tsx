import { redirect } from "next/navigation";

/** The OS opens on the dashboard. */
export default function RootPage() {
  redirect("/dashboard");
}
