import type { ReactNode } from "react";
import { Link, Outlet } from "react-router-dom";
import { Button } from "./ui";

interface LayoutProps {
  children?: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              S
            </span>
            <span className="text-lg font-semibold tracking-tight text-slate-900">Signal</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="hidden text-xs font-medium text-slate-400 sm:inline">
              Evidence-based candidate review
            </span>
            <Link to="/jobs/new">
              <Button className="px-3 py-1.5 text-xs">New job description</Button>
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">{children ?? <Outlet />}</main>
    </div>
  );
}
