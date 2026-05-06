import React from 'react';

type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost";
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
};

export const Button = ({ variant = "primary", children, className = "", onClick }: ButtonProps) => {
  const styles = {
    primary: "bg-leta-primary text-leta-white px-4 py-2 rounded-leta hover:opacity-90 transition-opacity",
    secondary: "border border-leta-primary text-leta-primary px-4 py-2 rounded-leta hover:bg-leta-gray-50 transition-colors",
    ghost: "text-leta-gray-700 px-4 py-2 hover:text-leta-gray-900 transition-colors",
  };

  return (
    <button className={`${styles[variant]} ${className}`} onClick={onClick}>
      {children}
    </button>
  );
};
