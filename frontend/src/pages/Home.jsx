import React from 'react';
import {
  Hero, StatutoryHero3D, StatutoryDomains, LetaIntro,
  PromoCards, VideoSection, HowItWorks, SecuritySection,
} from '../components/landing';
import { DynamicBackground } from '../components/effects';
import { ArrowRight, ShieldCheck, Scale, FileJson } from 'lucide-react';

const Home = () => {
  return (
    <div className="relative">
      <div className="film-grain" />
      <DynamicBackground />
      <Hero />
      <LetaIntro />
      <HowItWorks />
      <StatutoryDomains />
      <SecuritySection />
      <PromoCards />
      <VideoSection />
    </div>
  );
};

export default Home;
