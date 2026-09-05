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

// components/typography/index.ts re-exports this as `export { default as
// Heading } from './Heading'`, but this file only had a named export —
// mismatched, so importing anything at all from the top-level components
// barrel (src/components/index.ts, which `export * from './typography'`)
// threw a hard SyntaxError in Vite dev (esbuild's per-module ESM transform
// enforces this strictly); Rollup's production build tolerated it because
// nothing currently renders <Heading> anywhere; still real breakage
// waiting to happen the moment someone does.
export default Heading;
