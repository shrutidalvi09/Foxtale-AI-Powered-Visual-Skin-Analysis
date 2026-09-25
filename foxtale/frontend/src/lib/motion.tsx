import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ElementType, ReactNode } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** True once the element has scrolled into view (and stays true). */
export function useInView<T extends Element>(threshold = 0.12) {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined" || prefersReducedMotion()) {
      setSeen(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          obs.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

/** Fades and slides its children in when they scroll into view. `index` staggers siblings. */
export function Reveal({
  children, index = 0, as, className = "", innerRef,
}: {
  children: ReactNode;
  index?: number;
  as?: ElementType;
  className?: string;
  innerRef?: React.MutableRefObject<HTMLElement | null>;
}) {
  const [ref, seen] = useInView<HTMLElement>();
  const Tag = (as ?? "div") as ElementType;
  return (
    <Tag
      ref={(el: HTMLElement | null) => {
        ref.current = el;
        if (innerRef) innerRef.current = el;
      }}
      className={`reveal ${seen ? "in" : ""} ${className}`}
      style={{ "--i": index } as CSSProperties}
    >
      {children}
    </Tag>
  );
}

/** Eases a number from 0 to `value` when first shown. */
export function useCountUp(value: number, duration = 900, start = true): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!start) return;
    if (prefersReducedMotion() || value === 0) {
      setN(value);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, start]);
  return n;
}

export function CountUp({ value, duration = 900, suffix = "" }: { value: number; duration?: number; suffix?: string }) {
  const [ref, seen] = useInView<HTMLSpanElement>(0.3);
  const n = useCountUp(value, duration, seen);
  return <span ref={ref}>{n}{suffix}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/** Bumps a key each time `trigger` changes, so a CSS animation replays (e.g. star pop). */
export function usePulseKey(trigger: unknown): number {
  const [key, setKey] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setKey((k) => k + 1);
  }, [trigger]);
  return key;
}
