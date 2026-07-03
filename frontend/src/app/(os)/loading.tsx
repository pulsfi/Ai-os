import { Skeleton } from "@/components/ui/skeleton";

/** Shell-level route loading state (streamed while a page segment loads). */
export default function OsLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-10 rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-3 w-64" />
        </div>
      </div>
      <Skeleton className="h-52 w-full rounded-xl" />
    </div>
  );
}
