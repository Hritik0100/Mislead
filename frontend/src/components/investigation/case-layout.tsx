'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Users,
  FileText,
  AlertTriangle,
  Clock,
  GitBranch,
  Network,
  Image,
  Globe,
  Link2,
  BarChart3,
  FileBarChart,
  ArrowLeft,
} from 'lucide-react';

interface CaseLayoutProps {
  caseId: string;
  children: ReactNode;
}

const navigation = [
  { name: 'Overview', href: 'overview', icon: LayoutDashboard },
  { name: 'Accounts', href: 'accounts', icon: Users },
  { name: 'Posts', href: 'posts', icon: FileText },
  { name: 'Claims', href: 'claims', icon: AlertTriangle },
  { name: 'Timeline', href: 'timeline', icon: Clock },
  { name: 'Propagation', href: 'propagation', icon: GitBranch },
  { name: 'Coordination', href: 'coordination', icon: Network },
  { name: 'Media', href: 'media', icon: Image },
  { name: 'Sources', href: 'sources', icon: Globe },
  { name: 'Evidence', href: 'evidence', icon: Link2 },
  { name: 'Analysis', href: 'analysis', icon: BarChart3 },
  { name: 'Report', href: 'report', icon: FileBarChart },
];

export function CaseLayout({ caseId, children }: CaseLayoutProps) {
  const pathname = usePathname();
  const currentPath = pathname.split('/').pop() || 'overview';

  return (
    <div className="flex h-screen bg-gray-950">
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <Link
            href="/cases"
            className="flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-3 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Cases
          </Link>
          <h2 className="text-white font-semibold truncate">Case Details</h2>
          <p className="text-gray-500 text-xs font-mono mt-1 truncate">{caseId}</p>
        </div>

        <nav className="flex-1 overflow-y-auto p-2">
          {navigation.map((item) => {
            const isActive = currentPath === item.href;
            return (
              <Link
                key={item.href}
                href={`/cases/${caseId}/${item.href}`}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors mb-1',
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                )}
              >
                <item.icon
                  className={cn('w-4 h-4', isActive ? 'text-cyan-400' : 'text-gray-500')}
                />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
