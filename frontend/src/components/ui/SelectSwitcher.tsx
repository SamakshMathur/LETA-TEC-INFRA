import React from 'react';

export interface SwitcherOption {
  id: string;
  label: string;
}

interface SelectSwitcherProps {
  options: SwitcherOption[];
  value: string;
  onChange: (id: string) => void;
  variant?: 'primary' | 'subtle';
  layout?: 'flex' | 'grid' | 'scroll';
  columns?: number;
  className?: string;
}

const BASE = 'cursor-pointer transition-all text-center border font-medium';

const VARIANTS = {
  primary: {
    active:   'bg-[#67E8F9] text-[#07070A] border-transparent shadow-lg shadow-[#67E8F9]/10 scale-[1.01] font-semibold',
    inactive: 'bg-transparent text-[#6B7280] border-white/[0.05] hover:text-white hover:border-white/[0.1] hover:bg-white/[0.03]',
  },
  subtle: {
    active:   'bg-[rgba(79,183,197,0.18)] text-[#4FB7C5] border-[rgba(79,183,197,0.4)] font-bold',
    inactive: 'bg-[rgba(255,255,255,0.04)] text-[#6B7280] border-[rgba(255,255,255,0.06)] hover:text-white',
  },
};

const SelectSwitcher: React.FC<SelectSwitcherProps> = ({
  options,
  value,
  onChange,
  variant = 'primary',
  layout = 'flex',
  columns = 4,
  className = '',
}) => {
  const { active, inactive } = VARIANTS[variant];

  const itemClass = (id: string) =>
    `${BASE} py-2 px-3 rounded-lg text-[11px] ${id === value ? active : inactive}`;

  if (layout === 'grid') {
    return (
      <div className={`grid gap-2 ${className}`} style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
        {options.map(opt => (
          <button key={opt.id} onClick={() => onChange(opt.id)} className={itemClass(opt.id)}>
            {opt.label}
          </button>
        ))}
      </div>
    );
  }

  if (layout === 'scroll') {
    return (
      <div className={`flex gap-1.5 overflow-x-auto pb-1 ${className}`}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        {options.map(opt => (
          <button key={opt.id} onClick={() => onChange(opt.id)}
            className={`${itemClass(opt.id)} whitespace-nowrap flex-shrink-0 font-mono`}>
            {opt.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {options.map(opt => (
        <button key={opt.id} onClick={() => onChange(opt.id)} className={itemClass(opt.id)}>
          {opt.label}
        </button>
      ))}
    </div>
  );
};

export default SelectSwitcher;
