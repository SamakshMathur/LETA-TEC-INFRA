import React from 'react';

const FilmGrain = () => {
  return (
    <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden opacity-[0.03]">
      <div className="absolute inset-[-200%] h-[400%] w-[400%] animate-grain bg-[url('https://grainy-gradients.vercel.app/noise.svg')] bg-repeat"></div>
    </div>
  );
};

export default FilmGrain;
