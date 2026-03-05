'use client';

import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { resumeApi } from '@/lib/api';

interface ResumeStepProps {
  isUploaded: boolean;
  filename: string;
  onUploadComplete: (filename: string) => void;
  onChange: () => void;
}

export default function ResumeStep({
  isUploaded,
  filename,
  onUploadComplete,
  onChange,
}: ResumeStepProps) {
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      // Validate file type
      const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ];
      if (!validTypes.includes(file.type)) {
        toast.error('Invalid file type. Please upload PDF, DOC, or DOCX files only.');
        return;
      }

      // Validate file size (max 5MB)
      const maxSize = 5 * 1024 * 1024;
      if (file.size > maxSize) {
        toast.error('File too large. Maximum size is 5MB.');
        return;
      }

      try {
        await resumeApi.upload(file);
        onUploadComplete(file.name);
        toast.success('Resume uploaded successfully!');
      } catch (error: any) {
        const message = error.response?.data?.detail || 'Failed to upload resume';
        toast.error(message);
      }
    },
    [onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 5 * 1024 * 1024, // 5MB
    multiple: false,
  });

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <FileText className="h-8 w-8 text-linkedin-blue" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Upload Your Resume</h2>
        <p className="text-gray-600 mt-2">Upload your resume so we can tailor your applications</p>
      </div>

      {!isUploaded ? (
        <div className="card">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive ? 'border-linkedin-blue bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            {isDragActive ? (
              <p className="text-linkedin-blue font-medium">Drop your resume here...</p>
            ) : (
              <div>
                <p className="text-gray-700 font-medium mb-1">
                  Drag and drop your resume here, or click to browse
                </p>
                <p className="text-sm text-gray-500">Supports PDF, DOC, DOCX (max 5MB)</p>
              </div>
            )}
          </div>

          {fileRejections.length > 0 && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">
                {fileRejections[0].errors[0].code === 'file-too-large'
                  ? 'File too large. Maximum size is 5MB.'
                  : 'Invalid file type. Please upload PDF, DOC, or DOCX files only.'}
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="card bg-green-50 border-green-200">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-gray-900">Resume Uploaded</p>
              <p className="text-sm text-gray-600">{filename}</p>
            </div>
            <button onClick={onChange} className="text-sm text-gray-500 hover:text-gray-700">
              Change
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
