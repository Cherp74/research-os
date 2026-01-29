import { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, FileText, Award, Calendar } from 'lucide-react';
import type { SourceCardProps } from '../types';

export function SourceCard({ source }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getCredibilityColor = (score: number) => {
    if (score >= 0.7) return 'bg-green-100 text-green-800';
    if (score >= 0.4) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  const getSourceTypeIcon = (type: string) => {
    switch (type) {
      case 'academic':
        return '🎓';
      case 'news':
        return '📰';
      case 'blog':
        return '📝';
      default:
        return '🌐';
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{getSourceTypeIcon(source.source_type)}</span>
          
          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-gray-900 truncate">
              {source.title || 'Untitled Source'}
            </h4>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1 mt-1"
            >
              {source.domain}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getCredibilityColor(source.credibility_score)}`}>
            {(source.credibility_score * 100).toFixed(0)}%
          </span>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <FileText className="w-4 h-4" />
            {source.word_count.toLocaleString()} words
          </span>
          {source.has_citations && (
            <span className="flex items-center gap-1 text-green-600">
              <Award className="w-4 h-4" />
              Has citations
            </span>
          )}
          {source.has_methodology && (
            <span className="flex items-center gap-1 text-blue-600">
              <Calendar className="w-4 h-4" />
              Methodology
            </span>
          )}
        </div>

        {/* Credibility Factors */}
        {Object.keys(source.credibility_factors).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(source.credibility_factors).map(([key, value]) => (
              <span
                key={key}
                className="text-xs px-2 py-1 bg-gray-100 rounded text-gray-600"
              >
                {key.replace(/_/g, ' ')}: {(value * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        )}

        {/* Expand Button */}
        {source.text && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-3 text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Hide content
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                Show content
              </>
            )}
          </button>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && source.text && (
        <div className="px-4 pb-4">
          <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
            <p className="text-sm text-gray-700 whitespace-pre-wrap">
              {source.text.slice(0, 2000)}
              {source.text.length > 2000 && '...'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
