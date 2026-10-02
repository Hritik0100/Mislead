'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ChevronRight, Search, Bell, Settings } from 'lucide-react';
import { useCaseStore } from '@/lib/store';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export function Header() {
  const pathname = usePathname();
  const { currentCase } = useCaseStore();

  const pathSegments = pathname.split('/').filter(Boolean);

  const getBreadcrumbLabel = (segment: string, index: number) => {
    const labels: Record<string, string> = {
      cases: 'Cases',
      reports: 'Reports',
      overview: 'Overview',
      accounts: 'Accounts',
      posts: 'Posts',
      claims: 'Claims',
      timeline: 'Timeline',
      propagation: 'Propagation',
      coordination: 'Coordination',
      media: 'Media',
      sources: 'Sources',
      evidence: 'Evidence',
      analysis: 'Analysis',
      report: 'Report',
    };

    if (index === 1 && currentCase && segment === currentCase.id) {
      return currentCase.title;
    }

    return labels[segment] || segment;
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-cyber-border bg-cyber-surface/80 backdrop-blur-sm px-6">
      {/* Breadcrumbs */}
      <nav className="flex items-center space-x-1 text-sm">
        <Link
          href="/"
          className="text-cyber-text-dim hover:text-cyber-text transition-colors"
        >
          Home
        </Link>
        {pathSegments.map((segment, index) => (
          <React.Fragment key={segment}>
            <ChevronRight size={14} className="text-cyber-text-dim" />
            <Link
              href={`/${pathSegments.slice(0, index + 1).join('/')}`}
              className={cn(
                'transition-colors',
                index === pathSegments.length - 1
                  ? 'text-cyber-text font-medium'
                  : 'text-cyber-text-dim hover:text-cyber-text'
              )}
            >
              {getBreadcrumbLabel(segment, index)}
            </Link>
          </React.Fragment>
        ))}
      </nav>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-cyber-text-dim"
          />
          <input
            type="text"
            placeholder="Search investigations..."
            className="h-9 w-64 rounded-md border border-cyber-border bg-cyber-card pl-9 pr-4 text-sm text-cyber-text placeholder:text-cyber-text-dim focus:outline-none focus:ring-2 focus:ring-cyber-primary focus:border-transparent transition-colors"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-cyber-border bg-cyber-bg px-1.5 py-0.5 text-[10px] text-cyber-text-dim">
            /
          </kbd>
        </div>

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative">
          <Bell size={18} />
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-cyber-danger text-[10px] font-bold text-white">
            3
          </span>
        </Button>

        {/* Settings */}
        <Button variant="ghost" size="icon">
          <Settings size={18} />
        </Button>
      </div>
    </header>
  );
}
