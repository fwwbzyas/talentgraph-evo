import { motion, useInView, useReducedMotion } from "motion/react";
import { useRef } from "react";

export default function AnimatedContent({
  children,
  className = "",
  distance = 28,
  direction = "vertical",
  reverse = false,
  delay = 0,
  duration = 0.58,
}) {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const isInView = useInView(ref, { once: true, amount: 0.12 });
  const offset = reduceMotion ? 0 : (reverse ? -1 : 1) * distance;
  const initial = {
    opacity: reduceMotion ? 1 : 0,
    x: direction === "horizontal" ? offset : 0,
    y: direction === "vertical" ? offset : 0,
    filter: reduceMotion ? "none" : "blur(4px)",
  };

  return (
    <motion.div
      ref={ref}
      className={`rb-animated-content ${className}`}
      initial={initial}
      animate={
        isInView
          ? { opacity: 1, x: 0, y: 0, filter: "blur(0px)" }
          : initial
      }
      transition={{
        duration: reduceMotion ? 0 : duration,
        delay: reduceMotion ? 0 : delay,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
