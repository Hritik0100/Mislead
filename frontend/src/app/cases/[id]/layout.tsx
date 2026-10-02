'use client';

import { ReactNode } from 'react';
import { CaseLayout } from '@/components/investigation/case-layout';

export default function CaseIdLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  return <CaseLayout caseId={params.id}>{children}</CaseLayout>;
}
