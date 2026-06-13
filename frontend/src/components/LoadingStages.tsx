import { useEffect, useState } from "react";
import { ShieldCheck, ScanSearch, Scale, CheckSquare, Loader2 } from "lucide-react";

const STAGES = [
  { label: "Verifying documents",    Icon: ShieldCheck, delay: 0    },
  { label: "Extracting document data", Icon: ScanSearch, delay: 900  },
  { label: "Evaluating policy rules", Icon: Scale,      delay: 2200 },
  { label: "Finalising decision",     Icon: CheckSquare, delay: 3800 },
] as const;

export function LoadingStages() {
  const [visible, setVisible] = useState(0); // count of revealed stages

  useEffect(() => {
    const timers = STAGES.map((s, i) =>
      setTimeout(() => setVisible(v => Math.max(v, i + 1)), s.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="px-5 py-8">
      <p className="label mb-5">Processing claim</p>
      <div className="space-y-3">
        {STAGES.map((s, i) => {
          const revealed  = i < visible;
          const active    = i === visible - 1; // last revealed = currently running
          const done      = i < visible - 1;   // earlier stages = complete
          const isLast    = i === STAGES.length - 1;

          return (
            <div
              key={i}
              className="trace-event flex items-center gap-3"
              style={{
                animationDelay: `${s.delay}ms`,
                opacity: revealed ? 1 : 0,
                transition: "opacity 0.25s ease-out",
              }}
            >
              {/* Icon / spinner */}
              <div className="w-7 h-7 rounded flex items-center justify-center flex-shrink-0"
                style={{
                  background: done
                    ? "rgba(78,125,106,0.12)"
                    : active
                      ? "rgba(44,11,33,0.06)"
                      : "transparent",
                }}>
                {active && isLast
                  ? <Loader2 size={14} className="animate-spin text-aubergine opacity-60" />
                  : done
                    ? <s.Icon size={14} style={{ color: "#4e7d6a" }} />
                    : active
                      ? <s.Icon size={14} className="text-ink opacity-40" />
                      : <s.Icon size={14} className="text-ink-muted opacity-20" />
                }
              </div>

              {/* Label */}
              <span className={`text-sm font-sans transition-colors ${
                done   ? "text-ok"
                : active ? "text-ink"
                : "text-ink-muted opacity-40"
              }`}>
                {s.label}{active ? "…" : done ? "" : ""}
              </span>

              {/* Done tick */}
              {done && (
                <span className="font-mono text-[10px] text-ok ml-auto">done</span>
              )}
              {active && !isLast && (
                <Loader2 size={11} className="animate-spin text-ink-muted ml-auto" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
