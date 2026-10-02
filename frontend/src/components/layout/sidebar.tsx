'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import {
  LayoutDashboard,
  FolderOpen,
  FileText,
  Users,
  MessageSquare,
  AlertTriangle,
  Clock,
  GitBranch,
  Link2,
  Image,
  Database,
  Search,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Shield,
  Settings,
} from 'lucide-react';
import { useAuthStore, useCaseStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: number;
}

const mainNavItems: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: <LayoutDashboard size={18} /> },
  { label: 'Cases', href: '/cases', icon: <FolderOpen size={18} /> },
  { label: 'Reports', href: '/reports', icon: <FileText size={18} /> },
];

const caseNavItems: NavItem[] = [
  { label: 'Overview', href: '/overview', icon: <LayoutDashboard size={16} /> },
  { label: 'Accounts', href: '/accounts', icon: <Users size={16} /> },
  { label: 'Posts', href: '/posts', icon: <MessageSquare size={16} /> },
  { label: 'Claims', href: '/claims', icon: <AlertTriangle size={16} /> },
  { label: 'Timeline', href: '/timeline', icon: <Clock size={16} /> },
  { label: 'Propagation', href: '/propagation', icon: <GitBranch size={16} /> },
  { label: 'Coordination', href: '/coordination', icon: <Link2 size={16} /> },
  { label: 'Media', href: '/media', icon: <Image size={16} /> },
  { label: 'Sources', href: '/sources', icon: <Database size={16} /> },
  { label: 'Evidence', href: '/evidence', icon: <Search size={16} /> },
  { label: 'Analysis', href: '/analysis', icon: <BarChart3 size={16} /> },
  { label: 'Report', href: '/report', icon: <FileText size={16} /> },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const { currentCase } = useCaseStore();

  const caseId = currentCase?.id || 'case-1';
  const casePath = `/cases/${caseId}`;

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 h-screen border-r border-cyber-border bg-cyber-surface transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center justify-between border-b border-cyber-border px-4">
            {!collapsed && (
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyber-primary/20 border border-cyber-primary/30">
                  <Shield size={18} className="text-cyber-primary" />
                </div>
                <div>
                  <h1 className="text-sm font-bold tracking-wider text-cyber-text">
                    OSINT NEXUS
                  </h1>
                  <p className="text-[10px] text-cyber-text-dim tracking-wide">
                    INTELLIGENCE PLATFORM
                  </p>
                </div>
              </div>
            )}
            {collapsed && (
              <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-cyber-primary/20 border border-cyber-primary/30">
                <Shield size={18} className="text-cyber-primary" />
              </div>
            )}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="rounded-md p-1 text-cyber-text-dim hover:bg-cyber-card hover:text-cyber-text transition-colors"
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </div>

          {/* Main Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 py-4">
            <div className="space-y-1">
              {mainNavItems.map((item) => (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                        pathname === item.href
                          ? 'bg-cyber-primary/10 text-cyber-primary border border-cyber-primary/20'
                          : 'text-cyber-text-muted hover:bg-cyber-card hover:text-cyber-text border border-transparent'
                      )}
                    >
                      {item.icon}
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  </TooltipTrigger>
                  {collapsed && (
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  )}
                </Tooltip>
              ))}
            </div>

            {/* Case Navigation */}
            {currentCase && (
              <>
                <Separator className="my-4 bg-cyber-border" />
                <div className="mb-2">
                  {!collapsed ? (
                    <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-cyber-text-dim">
                      Active Case
                    </p>
                  ) : (
                    <Separator className="mx-3 mb-2" />
                  )}
                </div>
                <div className="space-y-1">
                  {caseNavItems.map((item) => (
                    <Tooltip key={item.href}>
                      <TooltipTrigger asChild>
                        <Link
                          href={`${casePath}${item.href}`}
                          className={cn(
                            'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                            pathname === `${casePath}${item.href}`
                              ? 'bg-cyber-primary/10 text-cyber-primary border border-cyber-primary/20'
                              : 'text-cyber-text-muted hover:bg-cyber-card hover:text-cyber-text border border-transparent'
                          )}
                        >
                          {item.icon}
                          {!collapsed && <span>{item.label}</span>}
                        </Link>
                      </TooltipTrigger>
                      {collapsed && (
                        <TooltipContent side="right">{item.label}</TooltipContent>
                      )}
                    </Tooltip>
                  ))}
                </div>
              </>
            )}
          </nav>

          {/* User Section */}
          <div className="border-t border-cyber-border p-3">
            {!collapsed ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyber-primary/20 border border-cyber-primary/30 text-xs font-semibold text-cyber-primary">
                    {user?.username?.[0]?.toUpperCase() || 'U'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-cyber-text truncate">
                      {user?.username || 'User'}
                    </p>
                    <p className="text-[10px] text-cyber-text-dim truncate">
                      {user?.role || 'analyst'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => {}}
                  >
                    <Settings size={14} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={logout}
                  >
                    <LogOut size={14} />
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyber-primary/20 border border-cyber-primary/30 text-xs font-semibold text-cyber-primary">
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={logout}
                >
                  <LogOut size={14} />
                </Button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}
