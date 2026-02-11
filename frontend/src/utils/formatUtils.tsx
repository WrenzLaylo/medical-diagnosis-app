import React from 'react';

/**
 * Format AI output text with minimal structure
 */
export const formatAIOutput = (text: string): React.ReactNode => {
  if (!text) return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];
  let listType: 'ul' | 'ol' | null = null;

  const flushList = () => {
    if (currentList.length > 0) {
      const ListTag = listType === 'ol' ? 'ol' : 'ul';
      elements.push(
        <ListTag key={elements.length} className={`${listType === 'ol' ? 'list-decimal' : 'list-disc'} list-inside space-y-1 my-2 ml-3`}>
          {currentList.map((item, idx) => (
            <li key={idx} className="text-gray-700">
              {formatInlineText(item)}
            </li>
          ))}
        </ListTag>
      );
      currentList = [];
      listType = null;
    }
  };

  const formatInlineText = (text: string): React.ReactNode => {
    return text.split(/(\*\*.*?\*\*|__.*?__)/g).map((part, idx) => {
      if (part.match(/^\*\*(.*?)\*\*$/)) {
        return <strong key={idx} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
      }
      if (part.match(/^__(.*?)__$/)) {
        return <strong key={idx} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  lines.forEach((line, idx) => {
    const trimmedLine = line.trim();

    if (!trimmedLine) {
      flushList();
      return;
    }

    // Headers
    const headerMatch = trimmedLine.match(/^(#{1,6})\s+(.+)$/);
    const boldHeaderMatch = trimmedLine.match(/^\*\*([A-Z\s]+)\*\*:?\s*$/);
    
    if (headerMatch) {
      flushList();
      const text = headerMatch[2];
      elements.push(
        <h4 key={idx} className="text-sm font-semibold text-gray-800 mt-3 mb-1">
          {text}
        </h4>
      );
      return;
    }

    if (boldHeaderMatch) {
      flushList();
      elements.push(
        <h4 key={idx} className="text-sm font-semibold text-gray-800 mt-2 mb-1">
          {boldHeaderMatch[1]}
        </h4>
      );
      return;
    }

    // Numbered lists
    const numberedMatch = trimmedLine.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch) {
      if (listType !== 'ol') {
        flushList();
        listType = 'ol';
      }
      currentList.push(numberedMatch[2]);
      return;
    }

    // Bulleted lists
    const bulletMatch = trimmedLine.match(/^[-*•]\s+(.+)$/);
    if (bulletMatch) {
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
      }
      currentList.push(bulletMatch[1]);
      return;
    }

    // Regular paragraph
    flushList();
    elements.push(
      <p key={idx} className="text-gray-700 my-1.5">
        {formatInlineText(trimmedLine)}
      </p>
    );
  });

  flushList();

  return <div className="clinical-content">{elements}</div>;
};

/**
 * Safe number formatting
 */
export const safeNumber = (value: any, defaultValue: number = 0): number => {
  if (value === null || value === undefined || value === '') {
    return defaultValue;
  }
  
  const num = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(num) || !isFinite(num)) {
    return defaultValue;
  }
  
  return num;
};

/**
 * Format percentage
 */
export const formatPercentage = (value: any, decimals: number = 1): string => {
  const num = safeNumber(value, 0);
  return `${(num * 100).toFixed(decimals)}%`;
};

/**
 * Get confidence color
 */
export const getConfidenceColor = (score: number): string => {
  const safeScore = safeNumber(score, 0);
  
  if (safeScore > 0.7) {
    return 'text-green-700';
  } else if (safeScore > 0.5) {
    return 'text-yellow-700';
  } else {
    return 'text-red-700';
  }
};

/**
 * Get confidence gradient
 */
export const getConfidenceGradient = (score: number): string => {
  const safeScore = safeNumber(score, 0);
  
  if (safeScore > 0.7) {
    return 'from-green-500 to-green-600';
  } else if (safeScore > 0.5) {
    return 'from-yellow-400 to-yellow-500';
  } else {
    return 'from-red-400 to-red-500';
  }
};