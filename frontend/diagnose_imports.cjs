const fs = require('fs');
const path = require('path');

function walk(dir) {
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(file => {
        file = path.join(dir, file);
        const stat = fs.statSync(file);
        if (stat && stat.isDirectory()) {
            results = results.concat(walk(file));
        } else {
            if (file.endsWith('.jsx') || file.endsWith('.js')) {
                results.push(file);
            }
        }
    });
    return results;
}

const allFiles = walk('./src');
const missing = [];

allFiles.forEach(f => {
    const content = fs.readFileSync(f, 'utf8');
    if (content.includes('<motion') && !content.includes('framer-motion')) {
        missing.push(f);
    }
});

if (missing.length > 0) {
    console.log("MISSING_IMPORTS:");
    missing.forEach(m => console.log(m));
} else {
    console.log("ALL_CLEAN");
}
