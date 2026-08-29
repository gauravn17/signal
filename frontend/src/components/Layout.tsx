import type { ReactNode } from "react";
import { Link, Outlet } from "react-router-dom";

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
          <span className="text-xs font-medium text-slate-400">Evidence-based candidate review</span>
        </div>
      </header>
      <main className="flex-1">{children ?? <Outlet />}</main>
    </div>
  );
}
