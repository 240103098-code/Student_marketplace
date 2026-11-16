import React from 'react';
import { Button } from './Button.jsx';

/**
 * "Page not found" page body. It owns the page's single h1 (pass `headingRef` so route changes can focus it).
 * Signed-in visitors get "Go to Marketplace", anonymous visitors get "Go to home".
 */
export function NotFound({ authed = false, navigate, headingRef, headingLevel = 1 }) {
  const Heading = `h${headingLevel}`;
  return (
    <div className="not-found">
      <a className="back-link" href="/" onClick={navigate}>Back to home</a>
      <div className="not-found__ticket">
        <p className="not-found__code" aria-hidden="true">404</p>
        <div className="not-found__text">
          <Heading ref={headingRef} tabIndex={-1}>Page not found</Heading>
          <p>We could not find this page. It may have moved, or the address may have a typo.</p>
        </div>
      </div>
      <div className="state-card__actions">
        {authed
          ? <><Button variant="primary" href="/marketplace" onClick={navigate}>Go to Marketplace</Button><Button variant="secondary" href="/my-listings" onClick={navigate}>My Listings</Button></>
          : <><Button variant="primary" href="/" onClick={navigate}>Go to home</Button><Button variant="secondary" href="/marketplace" onClick={navigate}>Browse Marketplace</Button></>}
      </div>
    </div>
  );
}
