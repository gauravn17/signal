import type { ReactNode } from "react";
import { Link, Outlet } from "react-router-dom";

interface LayoutProps {
  children?: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="border-b border-gray-200 px-4 py-3">
        <Link to="/" className="text-lg font-semibold">
          Signal
        </Link>
      </nav>
      <main className="flex-1">{children ?? <Outlet />}</main>
    </div>
  );
}
