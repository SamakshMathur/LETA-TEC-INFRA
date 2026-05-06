import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Landmark, Briefcase, FileText, Globe } from 'lucide-react';

const domains = [
  {
    id: 'gst',
    name: 'GST Intelligence',
    icon: FileText,
    desc: 'Goods & Services Tax',
    path: '/gst',
    gradient: 'from-[#0B7350] to-[#003B59]'
  },
  {
    id: 'income-tax',
    name: 'Income Tax',
    icon: Landmark,
    desc: 'Direct Tax Laws',
    path: '/income-tax',
    gradient: 'from-blue-600 to-blue-900'
  },
  {
    id: 'fema',
    name: 'FEMA Advisory',
    icon: Globe,
    desc: 'Foreign Exchange Mgmt',
    path: '/fema',
    gradient: 'from-emerald-600 to-teal-900'
  },
  {
    id: 'company-law',
    name: 'Company Law',
    icon: Briefcase,
    desc: 'Companies Act 2013',
    path: '/company-law',
    gradient: 'from-slate-700 to-slate-900'
  }
];

const DomainSelector = () => {
  return (
    <section className="py-16 bg-leta-white relative z-20 -mt-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {domains.map((domain, idx) => (
            <Link key={idx} to={domain.path} className="block group">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="relative overflow-hidden rounded-leta border border-leta-gray-100 shadow-lg bg-leta-white p-6 h-full flex flex-col items-center text-center hover:shadow-xl transition-all duration-150"
              >
                 {/* Hover Gradient Overlay */}
                 <div className={`absolute inset-0 bg-gradient-to-br ${domain.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-200`} />
                 
                 <div className="relative z-10 w-16 h-16 rounded-full bg-leta-gray-50 flex items-center justify-center text-leta-gray-900 mb-4 group-hover:bg-leta-white/20 group-hover:text-leta-gray-900 transition-all">
                    <domain.icon size={28} strokeWidth={1.5} />
                 </div>
                 
                 <h3 className="relative z-10 text-lg font-bold text-leta-gray-900 group-hover:text-leta-gray-900 transition-colors mb-1 font-sans">
                   {domain.name}
                 </h3>
                 <p className="relative z-10 text-xs font-medium text-leta-gray-600 uppercase tracking-wider group-hover:text-leta-gray-900/80 transition-colors">
                   {domain.desc}
                 </p>
 
                 <div className="mt-6 relative z-10 opacity-0 group-hover:opacity-100 transition-all duration-200">
                    <span className="text-[10px] font-pixel text-leta-gray-900 border border-leta-white/30 px-2 py-1 rounded-leta bg-leta-white/10 backdrop-blur-sm">
                        ACCESS DATABASE
                    </span>
                 </div>
              </motion.div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
};

export default DomainSelector;
