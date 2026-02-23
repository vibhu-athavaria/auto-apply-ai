'use client';

import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import DashboardLayout from '@/components/DashboardLayout';
import { resumeApi } from '@/lib/api';
import { FileText, Upload, Trash2, Download, File } from 'lucide-react';
import toast from 'react-hot-toast';

interface Resume {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadResumes();
  }, []);

  const loadResumes = async () => {
    setIsLoading(true);
    try {
      const data = await resumeApi.list();
      setResumes(data);
    } catch (error) {
      console.error('Failed to load resumes:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setIsUploading(true);
    try {
      await resumeApi.upload(file);
      toast.success('Resume uploaded successfully!');
      loadResumes();
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to upload resume';
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false,
  });

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <DashboardLayout>
      <div className="page-container">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Resumes</h1>
          <p className="text-gray-600">Upload and manage your resumes</p>
        </div>

        {/* Upload Area */}
        <div className="card mb-8">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-linkedin-blue bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            {isUploading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-linkedin-blue"></div>
                <span className="text-gray-600">Uploading...</span>
              </div>
            ) : isDragActive ? (
              <p className="text-linkedin-blue font-medium">Drop your resume here...</p>
            ) : (
              <div>
                <p className="text-gray-700 font-medium mb-1">
                  Drag and drop your resume here, or click to browse
                </p>
                <p className="text-sm text-gray-500">
                  Supports PDF, DOC, DOCX (max 10MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Resumes List */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Resumes</h2>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue"></div>
            </div>
          ) : resumes.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No resumes uploaded yet</p>
              <p className="text-sm text-gray-400">Upload your first resume to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {resumes.map((resume) => (
                <div
                  key={resume.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <File className="h-5 w-5 text-linkedin-blue" />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{resume.filename}</p>
                      <p className="text-sm text-gray-500">
                        {formatFileSize(resume.file_size)} • Uploaded {formatDate(resume.uploaded_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="p-2 text-gray-500 hover:text-linkedin-blue hover:bg-gray-100 rounded-lg transition-colors"
                      title="Download"
                    >
                      <Download className="h-5 w-5" />
                    </button>
                    <button
                      className="p-2 text-gray-500 hover:text-red-500 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
