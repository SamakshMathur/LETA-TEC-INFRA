import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Link2, Sparkles, Database, FileText } from 'lucide-react';

const NODES = [
  { id: 'core', label: 'LETA Core Reasoning Engine', x: 50, y: 50, isCore: true, type: 'CORE' },
  { id: 'gst', label: 'GST (Indirect Taxes)', x: 20, y: 25, isCore: false, type: 'STATUTE', desc: 'CGST Act, SGST Act, IGST Act, rules mapping, circular exemptions.' },
  { id: 'fema', label: 'FEMA', x: 15, y: 60, isCore: false, type: 'STATUTE', desc: 'Foreign Exchange Management Act compliance, cross-border regulations.' },
  { id: 'company', label: 'Company Law', x: 80, y: 30, isCore: false, type: 'STATUTE', desc: 'Companies Act 2013, filing procedures, director liabilities, compliance checks.' },
  { id: 'litigation', label: 'Litigation & Appeals', x: 85, y: 70, isCore: false, type: 'STATUTE', desc: 'Appellate, high court, and supreme court writ jurisdictions.' },
  { id: 'incometax', label: 'Income Tax', x: 48, y: 15, isCore: false, type: 'STATUTE', desc: 'Direct Tax, TDS rules, structural asset transfers, procedural audits.' },
  { id: 'circulars', label: 'Circulars & Orders', x: 30, y: 85, isCore: false, type: 'SUPPORTING', desc: 'CBIC orders, explanatory circular notifications, department directions.' },
  { id: 'caselaw', label: 'Judicial Case Laws', x: 65, y: 85, isCore: false, type: 'SUPPORTING', desc: 'Precedential jurisprudence, ratio decidendi extract indexing.' },
];

const CONNECTIONS = [
  { from: 'core', to: 'gst' },
  { from: 'core', to: 'fema' },
  { from: 'core', to: 'company' },
  { from: 'core', to: 'litigation' },
  { from: 'core', to: 'incometax' },
  { from: 'core', to: 'circulars' },
  { from: 'core', to: 'caselaw' },
  { from: 'gst', to: 'circulars' },
  { from: 'company', to: 'litigation' },
  { from: 'litigation', to: 'caselaw' },
];

const MemoryMap = () => {
  const [selectedNode, setSelectedNode] = useState(NODES[0]);
  const [hoveredNode, setHoveredNode] = useState(null);

  return (
    <section className="py-[80px] bg-[#000000] relative overflow-hidden border-b border-white/[0.03]">


      <div className="max-w-[1600px] mx-auto px-10 lg:px-20 relative z-10">
        
        {/* Section Header */}
        <div className="mb-16 text-center max-w-3xl mx-auto">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#67E8F9] mb-3">
            Knowledge Graph Topology
          </p>
          <h2 className="font-display font-bold text-3xl md:text-5xl text-white uppercase tracking-tight">
            Legal Intelligence Memory Map
          </h2>
          <p className="font-body text-[#A1AAB8] text-sm md:text-base mt-4 leading-relaxed font-light">
            An interconnected multi-jurisdictional network of Indian tax code, statutory logic, and judicial rulings, indexed and mapped continuously. Hover or click nodes to explore the network logic.
          </p>
        </div>

        {/* Network and Info Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          
          {/* SVG Map Canvas (Left/Center Column) */}
          <div className="lg:col-span-8 relative h-[480px] md:h-[540px] rounded-leta border border-white/[0.05] bg-[#000000] overflow-hidden shadow-[inset_0_0_40px_rgba(0,0,0,0.8)]">
            
            {/* SVG Relationship Connectors */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {CONNECTIONS.map((conn, idx) => {
                const fromNode = NODES.find(n => n.id === conn.from);
                const toNode = NODES.find(n => n.id === conn.to);
                
                if (!fromNode || !toNode) return null;

                const isHighlighted = 
                  hoveredNode === conn.from || hoveredNode === conn.to ||
                  selectedNode.id === conn.from || selectedNode.id === conn.to;

                return (
                  <motion.line
                    key={idx}
                    x1={`${fromNode.x}%`}
                    y1={`${fromNode.y}%`}
                    x2={`${toNode.x}%`}
                    y2={`${toNode.y}%`}
                    stroke={isHighlighted ? '#67E8F9' : 'rgba(255, 255, 255, 0.05)'}
                    strokeWidth={isHighlighted ? 1.5 : 1}
                    className="transition-all duration-500"
                  />
                );
              })}
            </svg>

            {/* Interactive Nodes */}
            {NODES.map((node) => {
              const isSelected = selectedNode.id === node.id;
              const isHovered = hoveredNode === node.id;

              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  className="absolute flex flex-col items-center focus:outline-none transition-transform duration-300"
                  style={{
                    left: `${node.x}%`,
                    top: `${node.y}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                >
                  {/* Floating node dot */}
                  <div
                    className={`rounded-xl transition-all duration-500 flex items-center justify-center ${
                      node.isCore
                        ? isSelected
                          ? 'w-14 h-14 bg-[#10141B] border-[#67E8F9] text-[#67E8F9] shadow-[0_0_30px_rgba(103,232,249,0.3)] scale-110'
                          : 'w-12 h-12 bg-[#10141B] border-white/[0.1] text-white'
                        : isSelected
                        ? 'w-8 h-8 bg-[#10141B] border-[#67E8F9] text-[#67E8F9] shadow-[0_0_15px_rgba(103,232,249,0.25)] scale-110'
                        : isHovered
                        ? 'w-7 h-7 bg-[#10141B] border-[#67E8F9]/50 text-[#67E8F9]'
                        : 'w-6 h-6 bg-[#000000] border-white/[0.08] text-[#52525B]'
                    } border`}
                  >
                    {node.isCore ? (
                      <Sparkles size={20} className={isSelected ? 'animate-pulse' : ''} />
                    ) : (
                      <div className={`w-1.5 h-1.5 rounded-full ${isSelected || isHovered ? 'bg-[#67E8F9]' : 'bg-[#52525B]'}`} />
                    )}
                  </div>

                  {/* Floating label */}
                  <span
                    className={`mt-2 font-mono text-[9px] uppercase tracking-wider font-bold whitespace-nowrap bg-[#000000]/80 px-2 py-0.5 rounded border ${
                      isSelected
                        ? 'text-white border-white/[0.1]'
                        : 'text-[#6B7280] border-transparent'
                    }`}
                  >
                    {node.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Detailed Node Information (Right Column Sidebar) */}
          <div className="lg:col-span-4 p-8 rounded-leta bg-[#10141B] border border-white/[0.04] min-h-[480px] flex flex-col justify-between">
            <div className="space-y-6">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase text-[#6B7280] border-b border-white/[0.03] pb-4">
                <Database size={12} className="text-[#67E8F9]" />
                <span>Node_Metadata_Explorer</span>
              </div>

              <div className="space-y-4">
                <span className="px-2.5 py-0.5 rounded text-[8px] font-bold font-mono tracking-widest bg-[#67E8F9]/10 border border-[#67E8F9]/20 text-[#67E8F9] uppercase">
                  {selectedNode.type} NODE
                </span>
                <h3 className="font-display font-bold text-2xl text-white">
                  {selectedNode.label}
                </h3>
                <p className="font-body text-[#A1AAB8] text-sm leading-relaxed font-light">
                  {selectedNode.desc || 'Central coordination logic engine. Maps interdependencies between compliance notifications, statutory sections, and historic rulings.'}
                </p>
              </div>

              {selectedNode.isCore && (
                <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.03] space-y-3">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-white">
                    <Link2 size={12} className="text-[#67E8F9]" />
                    <span>ENGINE TOPOLOGY</span>
                  </div>
                  <p className="text-[11px] font-mono text-[#6B7280] leading-relaxed">
                    Graph coordinates active on Direct Tax, FEMA, NCLT, and Goods & Services Tax indexes.
                  </p>
                </div>
              )}

              {!selectedNode.isCore && (
                <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.03] space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-white">
                    <FileText size={12} className="text-[#67E8F9]" />
                    <span>DEPENDENCY STATUS</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-[#67E8F9] rounded-full animate-pulse" />
                    <span className="font-mono text-[10px] text-emerald-400">INDEX SYNCHRONIZED</span>
                  </div>
                </div>
              )}
            </div>

            <div className="pt-6 border-t border-white/[0.03] flex items-center justify-between font-mono text-[10px] text-[#6B7280]">
              <span>ACTIVE LINKS</span>
              <span className="text-[#67E8F9] font-bold">10 INTERCONNECTIONS</span>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
};

export default MemoryMap;
