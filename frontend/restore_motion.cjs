const fs = require('fs');
const filesToFix = [
  'src/pages/About.jsx',
  'src/components/PromoCards.jsx',
  'src/components/SecuritySection.jsx',
  'src/components/effects/AmbientBackground.jsx'
];

filesToFix.forEach(f => {
  let text = fs.readFileSync(f, 'utf8');
  // Only add if not entirely sure it doesn't already have it
  if (!text.includes('framer-motion')) {
    text = "import { motion } from 'framer-motion';\n" + text;
    fs.writeFileSync(f, text);
    console.log(`Fixed ${f}`);
  }
});
