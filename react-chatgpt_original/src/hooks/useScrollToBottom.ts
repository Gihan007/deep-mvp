import { useRef, useEffect } from 'react';

/**
 * Custom hook for auto-scrolling to bottom of a container
 */
export function useScrollToBottom(dependencies: any[] = []) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, dependencies);

  return { bottomRef, scrollToBottom };
}
