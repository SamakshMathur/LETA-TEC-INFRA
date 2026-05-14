import React from 'react';
import { motion } from 'framer-motion';
import cx from 'classnames/bind';
import styles from './AnimatedButton.module.css';

const cn = cx.bind(styles);

const Button = ({ children, onClick, variant = 'primary', className, ...props }) => {
  return (
    <motion.button
      whileTap={{ opacity: 0.8 }}
      className={cn('animatedButton', variant, className)}
      onClick={onClick}
      {...props}
    >
      {children}
    </motion.button>
  );
};

export default Button;

