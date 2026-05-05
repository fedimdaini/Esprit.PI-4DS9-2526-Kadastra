import React from 'react';

const SecurityMap = () => {
  return (
    <div style={{ width: '100%', height: 'calc(100vh - 64px)', background: '#0f172a' }}>
      <iframe
        src="http://127.0.0.1:8000/api/contracts/map/"
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="Carte des Incidents"
      />
    </div>
  );
};

export default SecurityMap;
