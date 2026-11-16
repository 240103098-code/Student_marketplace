import React, { Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import './styles.css';

// Development builds only: /?ui-gallery shows every shared component. Dead-code-eliminated in production.
const Gallery = import.meta.env.DEV && new URLSearchParams(window.location.search).has('ui-gallery') ? lazy(() => import('./ui/Gallery.jsx')) : null;

createRoot(document.getElementById('root')).render(Gallery ? <Suspense fallback={null}><Gallery /></Suspense> : <App />);
