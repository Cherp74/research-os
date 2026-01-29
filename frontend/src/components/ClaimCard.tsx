import { useState } from 'react';
import { CheckCircle, XCircle, HelpCircle, ChevronDown, ChevronUp, Quote } from 'lucide-react';
import type { ClaimCardProps } from '../types';

export function ClaimCard({ claim, source }: ClaimCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getVerificationIcon = () => {
    if (claim.verified) {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (claim.verification_confidence > 0.3) {
      return <HelpCircle className="w-5 h-5 text-yellow-500" />;
    }
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const getVerificationColor = () => {
    if (claim.verified) return 'border-green-200 bg-green-50';
    if (claim.verification_confidence > 0.3) return 'border-yellow-200 bg-yellow-50';
    return 'border-red-200 bg-red-50';
  };

  const getVerificationLabel = () => {
    if (claim.verified) {
      return `Verified (${claim.verification_method})`;
    }
    return `Unverified (${(claim.verification_confidence * 100).toFixed(0)}% match)`;
  };

  return (
    <div className={`rounded-lg border-2 p-4 ${getVerificationColor()}`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        {getVerificationIcon()}
        
        <div className="flex-1">
          <p className="text-gray-900 font-medium">{claim.text}</p>
          
          {/* Metadata */}
          <div className="flex items-center gap-4 mt-2 text-sm">
            <span className={`font-medium ${claim.verified ? 'text-green-700' : 'text-yellow-700'}`}>
              {getVerificationLabel()}
            </span>
            
            {claim.confidence > 0 && (
              <span className="text-gray-500">
                Extraction confidence: {(claim.confidence * 100).toFixed(0)}%
              </span>
            )}
            
            {source && (
              <span className="text-gray-500">
                From: {source.domain}
              </span>
            )}
          </div>

          {/* Entities */}
          {claim.entities.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {claim.entities.map((entity, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 bg-white/70 rounded-full text-gray-600"
                >
                  {entity}
                </span>
              ))}
            </div>
          )}

          {/* Source Excerpt */}
          {claim.source_excerpt && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-3 text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              <Quote className="w-4 h-4" />
              {isExpanded ? (
                <>
                  <ChevronUp className="w-4 h-4" />
                  Hide source excerpt
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4" />
                  Show source excerpt
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Expanded Excerpt */}
      {isExpanded && claim.source_excerpt && (
        <div className="mt-4 pl-8">
          <div className="bg-white/70 rounded-lg p-4 border-l-4 border-primary-400">
            <p className="text-sm text-gray-700 italic">
              "{claim.source_excerpt}"
            </p>
            {source && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary-600 hover:text-primary-700 mt-2 inline-block"
              >
                View source →
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
