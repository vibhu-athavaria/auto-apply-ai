'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Briefcase, FileText, Search, Zap } from 'lucide-react';

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.push('/dashboard');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-linkedin-blue"></div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-white">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Briefcase className="h-8 w-8 text-linkedin-blue" />
            <span className="text-xl font-bold text-gray-900">LinkedIn Autopilot</span>
          </div>
          <div className="flex gap-4">
            <button
              onClick={() => router.push('/login')}
              className="btn-secondary"
            >
              Sign In
            </button>
            <button
              onClick={() => router.push('/register')}
              className="btn-primary"
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Automate Your LinkedIn Job Search
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Let AI find and apply to relevant jobs while you focus on what matters.
            Smart job matching, tailored resumes, and automated applications.
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => router.push('/register')}
              className="btn-primary text-lg px-8 py-3"
            >
              Start Free Trial
            </button>
            <button
              onClick={() => router.push('/login')}
              className="btn-secondary text-lg px-8 py-3"
            >
              Learn More
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="card text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <Search className="h-6 w-6 text-linkedin-blue" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Smart Job Discovery</h3>
            <p className="text-gray-600">
              Automatically find jobs matching your skills and preferences from LinkedIn.
            </p>
          </div>
          <div className="card text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <FileText className="h-6 w-6 text-linkedin-blue" />
            </div>
            <h3 className="text-lg font-semibold mb-2">AI Resume Tailoring</h3>
            <p className="text-gray-600">
              Get personalized resume and cover letter for each job application.
            </p>
          </div>
          <div className="card text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <Zap className="h-6 w-6 text-linkedin-blue" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Auto Apply</h3>
            <p className="text-gray-600">
              Apply to Easy Apply jobs automatically with your tailored documents.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Briefcase className="h-6 w-6 text-linkedin-blue" />
              <span className="font-semibold text-gray-900">LinkedIn Autopilot</span>
            </div>
            <p className="text-gray-500 text-sm">
              © 2024 LinkedIn Autopilot. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
