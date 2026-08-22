import React from 'react';
import {
  ScrollCinemaHero,
  IntelligenceFeed,
  StatutoryDomains,
  SimulatedWorkspace,
  SovereignTrust,
  CABotDemo,
} from '../components/landing';

const Home: React.FC = () => {
  return (
    <div className="relative overflow-hidden bg-[#000000]">

      {/* SECTION 01 — Cinematic scroll hero */}
      <ScrollCinemaHero />

      {/* SECTION 02 — Statutory Intelligence Modules */}
      <StatutoryDomains />

      {/* SECTION 04 — AI CA Bot Demo */}
      <CABotDemo />

      {/* SECTION 05 — Live Legal Intelligence Feed */}
      <IntelligenceFeed />

      {/* SECTION 06 — Operational Intelligence Workspace */}
      <SimulatedWorkspace />

      {/* SECTION 07 — Sovereign Trust Layer */}
      <SovereignTrust />

    </div>
  );
};

export default Home;
