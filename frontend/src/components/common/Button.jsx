import React from 'react';
import { motion } from 'framer-motion';

const Button = ({ children, onClick, variant = 'primary', className = '', ...props }) => {
  const baseStyles = "px-6 py-3 rounded-leta font-sans font-medium transition-all duration-150 text-sm tracking-wide disabled:opacity-50 disabled:cursor-not-allowed";
  
  const variants = {
    primary: "bg-brand-gradient text-leta-gray-900 shadow-lg focus:ring-2 focus:ring-leta-primary/50 hover:brightness-110 border border-transparent",
    secondary: "bg-transparent text-leta-gray-900 border border-sentinel-blue/20 hover:bg-sentinel-blue/5",
    outline: "bg-transparent text-leta-gray-900 border border-leta-white/30 hover:bg-leta-white/10"
  };

  return (
    <motion.button
      whileTap={{ opacity: 0.8 }}
      className={`${baseStyles} ${variants[variant]} ${className}`}
      onClick={onClick}
      {...props}
    >
      {children}
    </motion.button>
  );
};

export default Button;
