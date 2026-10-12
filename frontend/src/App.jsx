import React, { useEffect, useRef, useState } from 'react';

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
    description: 'Registration with your sdu.edu.kz university email will be available here soon.',
  },
  '/verify': {
    title: 'Verify your university email',
    description: 'Email verification will be available here soon. There is no code to enter in this preview.',
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
    const nextPath = event.currentTarget.getAttribute('href');
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
        <div className="preview-label">Preview · Coming soon</div>
        <h1 ref={heading} tabIndex={-1}>{view.title}</h1>
        <p className="intro">{view.description}</p>
        {path === '/' && (
          <div className="actions">
            <a className="button primary" href="/marketplace" onClick={navigate}>Explore marketplace</a>
            <a className="button secondary" href="/register" onClick={navigate}>Create an account</a>
          </div>
        )}
        {!views[path] && <a className="button secondary" href="/" onClick={navigate}>Back to home</a>}
        <aside className="preview-note" aria-label="Preview information">
          <span className="note-dot" aria-hidden="true" />
          <p>This is an early preview. Accounts, email verification, and listings are not available yet.</p>
        </aside>
      </main>
      <footer className="site-footer">Student Marketplace <span aria-hidden="true">·</span> For your university community</footer>
    </>
  );
}
