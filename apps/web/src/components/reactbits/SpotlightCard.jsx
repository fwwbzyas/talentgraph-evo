import { useRef } from "react";

export default function SpotlightCard({
  as: Component = "div",
  children,
  className = "",
  spotlightColor = "rgba(97, 221, 199, 0.16)",
  ...props
}) {
  const ref = useRef(null);

  const handlePointerMove = (event) => {
    const element = ref.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    element.style.setProperty("--mouse-x", `${event.clientX - rect.left}px`);
    element.style.setProperty("--mouse-y", `${event.clientY - rect.top}px`);
    element.style.setProperty("--spotlight-color", spotlightColor);
  };

  return (
    <Component
      ref={ref}
      className={`rb-spotlight ${className}`}
      onPointerMove={handlePointerMove}
      {...props}
    >
      {children}
    </Component>
  );
}
