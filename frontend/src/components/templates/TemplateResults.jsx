import React, { useState } from 'react';
import TemplateRow from './TemplateRow';
import TemplatePreviewModal from './TemplatePreviewModal';

const TemplateResults = ({ groups }) => {
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  if (!groups || groups.length === 0) {
    return (
      <div className="text-center py-20 text-gray-400">
        No templates found matching your criteria. Try adjusting your search.
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-12">
      {groups.map((group, index) => (
        <TemplateRow 
          key={index} 
          title={group.title} 
          templates={group.templates} 
          isHero={group.type === 'hero'}
          onPreview={(templateId) => setSelectedTemplate(templateId)}
        />
      ))}

      {/* Preview Modal is rendered at the root level of Results */}
      {selectedTemplate && (
        <TemplatePreviewModal 
          templateId={selectedTemplate} 
          onClose={() => setSelectedTemplate(null)} 
        />
      )}
    </div>
  );
};

export default TemplateResults;
