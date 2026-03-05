'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/lib/auth';
import { Briefcase, FileText, Search, Sparkles, TrendingUp } from 'lucide-react';

export default function DashboardPage() {
  const { user } = useAuth();

  const stats = [
    { name: 'Jobs Discovered', value: '0', icon: Briefcase, color: 'bg-blue-500' },
    { name: 'Applications Sent', value: '0', icon: FileText, color: 'bg-green-500' },
    { name: 'Search Profiles', value: '0', icon: Search, color: 'bg-purple-500' },
    { name: 'Response Rate', value: '0%', icon: TrendingUp, color: 'bg-orange-500' },
  ];

  return (
    <DashboardLayout>
      <div className="page-container">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Welcome back, {user?.email}</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat) => (
            <div key={stat.name} className="card">
              <div className="flex items-center">
                <div className={`${stat.color} p-3 rounded-lg`}>
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                  <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
            <div className="space-y-3">
              <a
                href="/dashboard/wizard"
                className="flex items-center gap-3 p-3 rounded-lg bg-linkedin-blue bg-opacity-10 hover:bg-opacity-20 transition-colors"
              >
                <Sparkles className="h-5 w-5 text-linkedin-blue" />
                <span className="font-medium text-linkedin-blue">Create Profile Wizard</span>
              </a>
              <a
                href="/dashboard/resumes"
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <FileText className="h-5 w-5 text-linkedin-blue" />
                <span className="font-medium text-gray-700">Upload Resume</span>
              </a>
              <a
                href="/dashboard/profiles"
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <Search className="h-5 w-5 text-linkedin-blue" />
                <span className="font-medium text-gray-700">Create Job Search Profile</span>
              </a>
              <a
                href="/dashboard/jobs"
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <Briefcase className="h-5 w-5 text-linkedin-blue" />
                <span className="font-medium text-gray-700">View Jobs</span>
              </a>
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Getting Started</h2>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-medium text-linkedin-blue">1</span>
                </div>
                <div>
                  <p className="font-medium text-gray-900">Upload your resume</p>
                  <p className="text-sm text-gray-500">Add your current resume to get started</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-medium text-linkedin-blue">2</span>
                </div>
                <div>
                  <p className="font-medium text-gray-900">Create a search profile</p>
                  <p className="text-sm text-gray-500">Define your job preferences and keywords</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-medium text-linkedin-blue">3</span>
                </div>
                <div>
                  <p className="font-medium text-gray-900">Start job search</p>
                  <p className="text-sm text-gray-500">Let us find matching jobs for you</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
