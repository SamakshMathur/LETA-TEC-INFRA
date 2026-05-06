import React from 'react';

type HeadingProps = {
  level?: "h1" | "h2" | "h3";
  children: React.ReactNode;
  className?: string;
};

export const Heading = ({ level = "h1", children, className = "" }: HeadingProps) => {
  const styles = {
    h1: "text-h1 font-heading font-bold",
    h2: "text-h2 font-heading font-semibold",
    h3: "text-h3 font-heading font-medium",
  };

  return <h1 className={`${styles[level]} ${className}`}>{children}</h1>;
};
