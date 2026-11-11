/** Compass mark: the Compassio motif (logo + score dial share this geometry). */
export function CompassMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={className}>
      <circle cx="16" cy="16" r="14.5" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
      <path d="M16 3.5v3M16 25.5v3M3.5 16h3M25.5 16h3" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
      <path d="M16 6.5 19.2 16 16 25.5 12.8 16Z" fill="currentColor" opacity="0.28" />
      <path d="M16 6.5 19.2 16h-6.4Z" fill="#7fd1a3" />
      <circle cx="16" cy="16" r="1.6" fill="currentColor" />
    </svg>
  );
}
