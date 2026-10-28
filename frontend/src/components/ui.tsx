import { useEffect, useRef, type ReactNode } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  X,
  ChevronRight,
} from "lucide-react";
import { Link } from "react-router-dom";
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="brand" aria-label="GNK ALGO home">
      <span className="brand-symbol">
        G<span>↗</span>
      </span>
      {!compact && (
        <span>
          GNK <b>ALGO</b>
          <small>INTELLIGENCE BEHIND EVERY TRADE</small>
        </span>
      )}
    </Link>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "green" | "red" | "amber" | "neutral";
}) {
  return (
    <span className={`badge ${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
export function Change({ value }: { value: number }) {
  const Icon = value >= 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={value >= 0 ? "positive change" : "negative change"}>
      <Icon size={13} />
      {value >= 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}
export function PageHead({
  title,
  subtitle,
  children,
  eyebrow,
}: {
  title: string;
  subtitle: string;
  children?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="page-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="head-actions">{children}</div>
    </div>
  );
}
export function Panel({
  title,
  extra,
  children,
  className = "",
}: {
  title: string;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}
export function Feedback({
  error,
  success,
  busy,
}: {
  error?: string;
  success?: string;
  busy?: boolean;
}) {
  return (
    <>
      {busy && (
        <p className="feedback" role="status">
          Processing paper request…
        </p>
      )}
      {error && (
        <p className="feedback error" role="alert">
          <CircleAlert size={16} />
          {error}
        </p>
      )}
      {success && (
        <p className="feedback success" role="status">
          <CheckCircle2 size={16} />
          {success}
        </p>
      )}
    </>
  );
}
export function Empty({
  title = "Nothing here yet",
  detail = "Your paper trading activity will appear here.",
  children,
}: {
  title?: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">⌁</div>
      <h3>{title}</h3>
      <p>{detail}</p>
      {children}
    </div>
  );
}
export function TextLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" to={to}>
      {children}
      <ChevronRight size={14} />
    </Link>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef(document.activeElement as HTMLElement | null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      queueMicrotask(() => {
        if (opener.current?.isConnected) opener.current.focus();
      });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon-btn" aria-label="Close dialog" onClick={close}>
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Chart({
  period = "1D",
  compact = false,
}: {
  period?: string;
  compact?: boolean;
}) {
  const phase = [...period].reduce((n, c) => n + c.charCodeAt(0), 0);
  const points = Array.from(
    { length: 75 },
    (_, i) =>
      `${i * 10},${145 - i * 0.95 + Math.sin(i * 1.5 + phase) * 11 + Math.sin(i * 0.45 + phase / 7) * 17 + (period === "1W" ? Math.cos(i * 0.7) * 16 : 0)}`,
  ).join(" ");
  return (
    <svg
      className={compact ? "spark" : "main-chart"}
      viewBox="0 0 740 190"
      role="img"
      aria-label={`Fictional ${period} performance chart`}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient
          id={compact ? "sparkFill" : "chartFill"}
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop offset="0%" stopColor="#b4f17d" stopOpacity=".17" />
          <stop offset="100%" stopColor="#b4f17d" stopOpacity="0" />
        </linearGradient>
      </defs>
      {!compact &&
        [20, 65, 110, 155].map((y) => (
          <line
            key={y}
            x1="0"
            x2="740"
            y1={y}
            y2={y}
            stroke="currentColor"
            strokeDasharray="3 5"
          />
        ))}
      <polygon
        points={`0,190 ${points} 740,190`}
        fill={`url(#${compact ? "sparkFill" : "chartFill"})`}
      />
      <polyline
        points={points}
        fill="none"
        stroke="#b4f17d"
        strokeWidth={compact ? 4 : 2}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
