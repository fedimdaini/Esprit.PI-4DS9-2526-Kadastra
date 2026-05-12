import React, { useState, useEffect } from 'react';

export default function ImageGallery({ images, titre }) {
  const [validImages, setValidImages] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkImages();
  }, [images]);

  async function checkImages() {
    if (!images || images.length === 0) {
      setLoading(false);
      return;
    }

    const valid = [];

    for (const url of images) {
      try {
        const img = new Image();
        img.src = url;

        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          setTimeout(reject, 2000);
        });

        valid.push(url);
      } catch {
        continue; // ✅ FIXED (was break)
      }
    }

    setValidImages(valid);
    setLoading(false);
  }

  if (loading) {
    return (
      <div style={{ 
        width: '100%', 
        height: 200, 
        background: '#f0f0f0', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        borderRadius: 12 
      }}>
        Chargement...
      </div>
    );
  }

  if (validImages.length === 0) {
    return (
      <div style={{ 
        width: '100%', 
        height: 200, 
        background: '#f0f0f0', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        borderRadius: 12, 
        color: '#999' 
      }}>
        📷 Aucune image
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      
      <img 
        src={validImages[currentIndex]} 
        alt={titre || `Image ${currentIndex + 1}`}
        style={{ 
          width: '100%', 
          height: 200, 
          objectFit: 'cover', 
          borderRadius: 12 
        }} 
      />

      {validImages.length > 1 && (
        <>
          <button 
            onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
            disabled={currentIndex === 0}
            style={{ 
              position: 'absolute', 
              left: 10, 
              top: '50%', 
              transform: 'translateY(-50%)',
              background: 'rgba(0,0,0,0.6)', 
              color: '#fff', 
              border: 'none', 
              padding: '8px 12px', 
              borderRadius: 50, 
              cursor: 'pointer',
              opacity: currentIndex === 0 ? 0.3 : 1
            }}
          >
            ‹
          </button>

          <button 
            onClick={() => setCurrentIndex(Math.min(validImages.length - 1, currentIndex + 1))}
            disabled={currentIndex === validImages.length - 1}
            style={{ 
              position: 'absolute', 
              right: 10, 
              top: '50%', 
              transform: 'translateY(-50%)',
              background: 'rgba(0,0,0,0.6)', 
              color: '#fff', 
              border: 'none', 
              padding: '8px 12px', 
              borderRadius: 50, 
              cursor: 'pointer',
              opacity: currentIndex === validImages.length - 1 ? 0.3 : 1
            }}
          >
            ›
          </button>

          <div style={{ 
            position: 'absolute', 
            bottom: 10, 
            right: 10,
            background: 'rgba(0,0,0,0.6)', 
            color: '#fff', 
            padding: '4px 10px', 
            borderRadius: 12, 
            fontSize: 12 
          }}>
            {currentIndex + 1} / {validImages.length}
          </div>
        </>
      )}

    </div>
  );
}