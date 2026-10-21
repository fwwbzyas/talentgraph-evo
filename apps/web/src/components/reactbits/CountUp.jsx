import { useInView, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import { useCallback, useEffect, useRef } from "react";

export default function CountUp({
  to,
  from = 0,
  delay = 0,
  duration = 1.4,
  className = "",
  separator = "",
  suffix = "",
}) {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const motionValue = useMotionValue(from);
  const springValue = useSpring(motionValue, {
    damping: 24,
    stiffness: 150,
    mass: 0.8,
  });
  const isInView = useInView(ref, { once: true, margin: "0px" });
  const decimals = Math.max(
    String(from).split(".")[1]?.length || 0,
    String(to).split(".")[1]?.length || 0,
  );
  const formatValue = useCallback(
    (latest) => {
      const formatted = Intl.NumberFormat("en-US", {
        useGrouping: Boolean(separator),
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(latest);
      return `${separator ? formatted.replace(/,/g, separator) : formatted}${suffix}`;
    },
    [decimals, separator, suffix],
  );

  useEffect(() => {
    if (ref.current) ref.current.textContent = formatValue(from);
  }, [formatValue, from]);

  useEffect(() => {
    if (!isInView) return undefined;
    if (reduceMotion) {
      if (ref.current) ref.current.textContent = formatValue(to);
      return undefined;
    }
    const timer = window.setTimeout(
      () => motionValue.set(to),
      delay * 1000,
    );
    const settleTimer = window.setTimeout(() => {
      springValue.jump(to);
      if (ref.current) ref.current.textContent = formatValue(to);
    }, (delay + duration) * 1000);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(settleTimer);
    };
  }, [delay, duration, formatValue, isInView, motionValue, reduceMotion, springValue, to]);

  useEffect(
    () =>
      springValue.on("change", (latest) => {
        if (ref.current) ref.current.textContent = formatValue(latest);
      }),
    [formatValue, springValue],
  );

  return <span className={className} ref={ref} />;
}
