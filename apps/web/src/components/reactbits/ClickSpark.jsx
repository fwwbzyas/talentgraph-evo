import { useCallback, useEffect, useRef } from "react";

export default function ClickSpark({
  children,
  className = "",
  sparkColor = "#b9ef5b",
  sparkCount = 8,
  sparkRadius = 20,
  duration = 420,
}) {
  const canvasRef = useRef(null);
  const sparksRef = useRef([]);
  const animationRef = useRef(null);

  const draw = useCallback(
    (timestamp) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
      sparksRef.current = sparksRef.current.filter((spark) => {
        const progress = (timestamp - spark.startTime) / duration;
        if (progress >= 1) return false;
        const eased = progress * (2 - progress);
        const distance = eased * sparkRadius;
        const length = 8 * (1 - eased);
        const x1 = spark.x + distance * Math.cos(spark.angle);
        const y1 = spark.y + distance * Math.sin(spark.angle);
        context.strokeStyle = sparkColor;
        context.lineWidth = 1.5;
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(
          x1 + length * Math.cos(spark.angle),
          y1 + length * Math.sin(spark.angle),
        );
        context.stroke();
        return true;
      });
      animationRef.current = sparksRef.current.length
        ? requestAnimationFrame(draw)
        : null;
    },
    [duration, sparkColor, sparkRadius],
  );

  useEffect(
    () => () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    },
    [],
  );

  const handleClick = (event) => {
    const canvas = canvasRef.current;
    if (!canvas || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const now = performance.now();
    sparksRef.current.push(
      ...Array.from({ length: sparkCount }, (_, index) => ({
        x: (event.clientX - rect.left) * scaleX,
        y: (event.clientY - rect.top) * scaleY,
        angle: (Math.PI * 2 * index) / sparkCount,
        startTime: now,
      })),
    );
    if (!animationRef.current) animationRef.current = requestAnimationFrame(draw);
  };

  return (
    <div className={`rb-click-spark ${className}`} onClick={handleClick}>
      <canvas ref={canvasRef} width="360" height="120" aria-hidden="true" />
      {children}
    </div>
  );
}
