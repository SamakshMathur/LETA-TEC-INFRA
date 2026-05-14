import React from 'react';
import cx from 'classnames/bind';
import styles from './Heading.module.css';

const cn = cx.bind(styles);

type HeadingProps = {
  level?: "h1" | "h2" | "h3";
  children: React.ReactNode;
  className?: string;
};

export const Heading = ({ level = "h1", children, className }: HeadingProps) => {
  return (
    <h1 className={cn('heading', level, className)}>
      {children}
    </h1>
  );
};
