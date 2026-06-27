import React from "react";

export const AuroraBackground = ({
  children,
  showRadialGradient = true,
  animationSpeed = 40,
  className = "",
  ...props
}) => {
  return (
    <div className={`relative ${className}`} {...props}>
      <div className="absolute inset-0 overflow-hidden">
        <div
          className="aurora-layer"
          style={{
            "--animation-speed": `${animationSpeed}s`,
            maskImage: showRadialGradient
              ? "radial-gradient(ellipse at 50% 0%, black 30%, transparent 75%)"
              : undefined,
            WebkitMaskImage: showRadialGradient
              ? "radial-gradient(ellipse at 50% 0%, black 30%, transparent 75%)"
              : undefined,
          }}
        />
      </div>
      {children}
    </div>
  );
};

export default AuroraBackground;
