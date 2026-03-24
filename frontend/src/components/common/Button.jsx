import React from 'react';
import { motion } from 'framer-motion';

const Button = ({ children, onClick, variant = 'primary', className = '', ...props }) => {
  const baseStyles = "px-6 py-3 rounded font-sans font-medium transition-all duration-300 transform active:scale-95 text-sm tracking-wide disabled:opacity-50 disabled:cursor-not-allowed";
  
  const variants = {
    primary: "bg-brand-gradient text-white shadow-lg hover:shadow-sentinel-green/25 hover:brightness-110 border border-transparent",
    secondary: "bg-transparent text-sentinel-blue border border-sentinel-blue/20 hover:bg-sentinel-blue/5",
    outline: "bg-transparent text-white border border-white/30 hover:bg-white/10"
  };

  return (
    <motion.button
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.98 }}
      className={`${baseStyles} ${variants[variant]} ${className}`}
      onClick={onClick}
      {...props}
    >
      {children}
    </motion.button>
  );
};

export default Button;
