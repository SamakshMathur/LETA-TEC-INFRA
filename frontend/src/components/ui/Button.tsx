import React from 'react';
import cx from 'classnames/bind';
import styles from './Button.module.css';

const cn = cx.bind(styles);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  children: React.ReactNode;
};

export const Button = ({ variant = "primary", children, className, ...props }: ButtonProps) => {
  return (
    <button 
      className={cn('button', variant, className)} 
      {...props}
    >
      {children}
    </button>
  );
};
