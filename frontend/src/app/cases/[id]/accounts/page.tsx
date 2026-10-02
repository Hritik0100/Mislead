'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Search,
  ExternalLink,
  CheckCircle,
  XCircle,
  Users,
  Loader2,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { formatDate, formatNumber } from '@/lib/utils';
import api from '@/lib/api';
import { Account } from '@/lib/types';

export default function CaseAccountsPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { accounts, setAccounts, loading, setLoading } = useInvestigationStore();
  const [search, setSearch] = useState('');
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);

  useEffect(() => {
    fetchAccounts();
  }, [caseId]);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/accounts`);
      setAccounts(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredAccounts = accounts.filter(
    (account) =>
      account.username.toLowerCase().includes(search.toLowerCase()) ||
      account.display_name?.toLowerCase().includes(search.toLowerCase())
  );

  const getPlatformColor = (platform: string) => {
    const colors: Record<string, string> = {
      twitter: '#1DA1F2',
      youtube: '#FF0000',
      telegram: '#0088cc',
      matrix: '#0DBD8B',
      web: '#6366f1',
    };
    return colors[platform.toLowerCase()] || '#6b7280';
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Accounts</h1>
          <p className="text-gray-400 mt-1">{accounts.length} accounts discovered</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search accounts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 pr-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : filteredAccounts.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No accounts found</p>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-400 text-sm border-b border-gray-800">
                    <th className="p-4 font-medium">Account</th>
                    <th className="p-4 font-medium">Platform</th>
                    <th className="p-4 font-medium">Followers</th>
                    <th className="p-4 font-medium">Verified</th>
                    <th className="p-4 font-medium">Credibility</th>
                    <th className="p-4 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {filteredAccounts.map((account) => (
                    <tr
                      key={account.id}
                      className={`hover:bg-gray-800/50 cursor-pointer ${
                        selectedAccount?.id === account.id ? 'bg-gray-800' : ''
                      }`}
                      onClick={() => setSelectedAccount(account)}
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-white font-medium">
                            {account.avatar_url ? (
                              <img
                                src={account.avatar_url}
                                alt={account.username}
                                className="w-full h-full rounded-full object-cover"
                              />
                            ) : (
                              account.username.charAt(0).toUpperCase()
                            )}
                          </div>
                          <div>
                            <p className="text-white font-medium">{account.display_name || account.username}</p>
                            <p className="text-gray-500 text-sm">@{account.username}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span
                          className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium"
                          style={{
                            backgroundColor: `${getPlatformColor(account.platform)}20`,
                            color: getPlatformColor(account.platform),
                          }}
                        >
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: getPlatformColor(account.platform) }}
                          />
                          {account.platform}
                        </span>
                      </td>
                      <td className="p-4 text-gray-300 text-sm">
                        {account.followers ? formatNumber(account.followers) : 'N/A'}
                      </td>
                      <td className="p-4">
                        {account.verified ? (
                          <CheckCircle className="w-5 h-5 text-green-400" />
                        ) : (
                          <XCircle className="w-5 h-5 text-gray-600" />
                        )}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-cyan-500 rounded-full"
                              style={{
                                width: `${(account.credibility_score || 0) * 100}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs text-gray-400">
                            {((account.credibility_score || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td className="p-4">
                        {account.profile_url && (
                          <a
                            href={account.profile_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-white"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedAccount ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Account Details</h3>
              
              <div className="text-center mb-4">
                <div className="w-20 h-20 rounded-full bg-gray-700 mx-auto mb-3 flex items-center justify-center text-2xl font-bold text-white">
                  {selectedAccount.avatar_url ? (
                    <img
                      src={selectedAccount.avatar_url}
                      alt={selectedAccount.username}
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    selectedAccount.username.charAt(0).toUpperCase()
                  )}
                </div>
                <p className="text-white font-medium">{selectedAccount.display_name || selectedAccount.username}</p>
                <p className="text-gray-500 text-sm">@{selectedAccount.username}</p>
              </div>

              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-1">Bio</p>
                  <p className="text-white text-sm">{selectedAccount.bio || 'No bio available'}</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-white">
                      {selectedAccount.followers ? formatNumber(selectedAccount.followers) : '0'}
                    </p>
                    <p className="text-gray-400 text-xs">Followers</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-white">
                      {selectedAccount.following ? formatNumber(selectedAccount.following) : '0'}
                    </p>
                    <p className="text-gray-400 text-xs">Following</p>
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Similarity Candidates</p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm">@similar_user_1</span>
                      <span className="text-cyan-400 text-xs">85% match</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm">@similar_user_2</span>
                      <span className="text-cyan-400 text-xs">72% match</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Activity Timeline</p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-gray-300">
                      <div className="w-2 h-2 rounded-full bg-blue-500" />
                      First observed: {formatDate(selectedAccount.created_at)}
                    </div>
                    <div className="flex items-center gap-2 text-gray-300">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      Last active: {formatDate(selectedAccount.updated_at)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <Users className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select an account to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
