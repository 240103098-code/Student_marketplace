import React, { useEffect, useRef, useState } from 'react';
import { RegistrationForm, VerificationForm } from './AccountForms.jsx';

const views = {
  '/': {
    title: 'Your campus marketplace',
    description: 'A simple place for students to discover useful things and connect with sellers. We are getting it ready for you.',
  },
  '/login': {
    title: 'Sign in',
    description: 'Sign-in will be available here soon. This preview does not collect account details.',
  },
  '/register': {
    title: 'Create your account',
    description: 'Use your university email to create an account, then verify it with the code sent by email.',
  },
  '/verify': {
    title: 'Verify your university email',
    description: 'Enter your university email and the six-digit code from your inbox. You can edit the email or request a replacement.',
  },
  '/marketplace': {
    title: 'Marketplace',
    description: 'Listings will appear here when the marketplace is ready. Access will require a verified university email.',
  },
};

const navigation = [
  ['/', 'Home'],
  ['/marketplace', 'Marketplace'],
  ['/login', 'Sign in'],
  ['/register', 'Register'],
  ['/verify', 'Verify email'],
];

export function App() {
  const [path, setPath] = useState(window.location.pathname);
  const heading = useRef(null);
  const previousPath = useRef(path);
  const [verification, setVerification] = useState({ email: '', cooldowns: {} });

  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);

  useEffect(() => {
    if (previousPath.current !== path) {
      heading.current?.focus();
      previousPath.current = path;
    }
  }, [path]);

  function navigate(event) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    goTo(event.currentTarget.getAttribute('href'));
  }

  function goTo(nextPath) {
    if (window.location.pathname !== nextPath) window.history.pushState(null, '', nextPath);
    setPath(nextPath);
  }

  const view = views[path] || {
    title: 'Page not found',
    description: 'We could not find this page. Head back home to explore the preview.',
  };

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="/" onClick={navigate}>Student Marketplace</a>
          <nav aria-label="Main navigation">
            {navigation.map(([href, label]) => (
              <a key={href} href={href} onClick={navigate} aria-current={path === href ? 'page' : undefined}>{label}</a>
            ))}
          </nav>
        </div>
      </header>
      <main id="main" className="main-content" tabIndex={-1}>
        <div className="preview-label">{['/register', '/verify'].includes(path) ? 'University accounts' : 'Preview · Coming soon'}</div>
        <h1 ref={heading} tabIndex={-1}>{view.title}</h1>
        <p className="intro">{view.description}</p>
        {path === '/register' && <RegistrationForm navigate={navigate} onRegistered={(email, deadline) => {
          setVerification(previous => ({ email, cooldowns: { ...previous.cooldowns, [email]: deadline } }));
          goTo('/verify');
        }} />}
        {path === '/verify' && <VerificationForm initialEmail={verification.email} cooldowns={verification.cooldowns} navigate={navigate} onCooldown={(email, deadline) => setVerification(previous => ({ email, cooldowns: { ...previous.cooldowns, [email]: deadline } }))} />}
        {path === '/' && (
          <div className="actions">
            <a className="button primary" href="/marketplace" onClick={navigate}>Explore marketplace</a>
            <a className="button secondary" href="/register" onClick={navigate}>Create an account</a>
          </div>
        )}
        {!views[path] && <a className="button secondary" href="/" onClick={navigate}>Back to home</a>}
        <aside className="preview-note" aria-label="Preview information">
          <span className="note-dot" aria-hidden="true" />
          <p>Registration and email verification are available. Sign-in screens and marketplace listings are still being prepared.</p>
        </aside>
      </main>
      <footer className="site-footer">Student Marketplace <span aria-hidden="true">·</span> For your university community</footer>
    </>
  );
}
