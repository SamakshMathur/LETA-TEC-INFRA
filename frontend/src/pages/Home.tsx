import React from 'react';
import {
  SovereignHero,
  IntelligenceEngine,
  IntelligenceFeed,
  MemoryMap,
  StatutoryDomains,
  SimulatedWorkspace,
  SovereignTrust,
} from '../components/landing';
import { DynamicBackground } from '../components/effects';

const Home: React.FC = () => {
  return (
    <div className="relative overflow-hidden bg-[#070B11]">
      <DynamicBackground />
      
      {/* SECTION 01 — Sovereign Hero Interface */}
      <SovereignHero />
      
      {/* SECTION 02 — Statutory Intelligence Modules */}
      <StatutoryDomains />
      
      {/* SECTION 03 — Statutory Intelligence Engine */}
      <IntelligenceEngine />
      
      {/* SECTION 04 — Live Legal Intelligence Feed */}
      <IntelligenceFeed />
      
      {/* SECTION 05 — Legal Intelligence Memory Map */}
      <MemoryMap />
      
      {/* SECTION 06 — Operational Intelligence Workspace */}
      <SimulatedWorkspace />
      
      {/* SECTION 07 — Sovereign Trust Layer */}
      <SovereignTrust />
    </div>
  );
};

export default Home;
