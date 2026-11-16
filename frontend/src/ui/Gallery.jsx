import React, { useRef, useState } from 'react';
import { Button } from './Button.jsx';
import { Field } from './Field.jsx';
import { StatusBadge, STATUS_TONES } from './StatusBadge.jsx';
import { Skeleton, Loading } from './Skeleton.jsx';
import { Notice, Toast } from './Notice.jsx';
import { Dialog } from './Dialog.jsx';
import { EmptyState } from './EmptyState.jsx';
import { ErrorState } from './ErrorState.jsx';
import { NotFound } from './NotFound.jsx';
import { PriceTag } from './PriceTag.jsx';

/**
 * Every shared component and variant on one page. It is rendered by the Vitest suite (ui/Gallery.test.jsx)
 * and, in development builds only, at /?ui-gallery (see main.jsx). It is never reachable in production builds.
 */
export function Gallery() {
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState(false);
  const opener = useRef(null);
  return (
    <main className="main-content" id="main">
      <h1>Shared components</h1>
      <p className="intro">Campus Paper building blocks with every variant and state.</p>

      <section aria-labelledby="g-buttons"><h2 id="g-buttons">Button</h2>
        <div className="actions">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" size="large">Large primary</Button>
          <Button variant="primary" loading loadingLabel="Saving...">Save</Button>
          <Button variant="secondary" disabled>Disabled</Button>
          <Button variant="primary" href="/marketplace">Link button</Button>
        </div>
      </section>

      <section aria-labelledby="g-fields"><h2 id="g-fields">Field</h2>
        <div style={{ maxWidth: 420 }}>
          <Field label="University email" hint="Use your sdu.edu.kz address." type="email" />
          <Field label="Price" required hint="Amount in KZT." inputMode="decimal" />
          <Field label="Title" required error="Enter a title of 1 to 120 characters." defaultValue="" />
          <Field label="Description" as="textarea" rows={3} />
          <Field label="Category" as="select"><option>Electronics</option><option>Books</option></Field>
          <Field label="Locked" disabled defaultValue="Read only" />
        </div>
      </section>

      <section aria-labelledby="g-badges"><h2 id="g-badges">StatusBadge</h2>
        <div className="actions">{STATUS_TONES.map((status) => <StatusBadge key={status} status={status} />)}</div>
        <p><PriceTag amount="12 500" /></p>
      </section>

      <section aria-labelledby="g-skeleton"><h2 id="g-skeleton">Skeleton</h2>
        <Loading label="Loading"><Skeleton shape="line" lines={3} /><Skeleton shape="block" height={80} /><Skeleton shape="card" /></Loading>
      </section>

      <section aria-labelledby="g-notice"><h2 id="g-notice">Notice and Toast</h2>
        <Notice tone="info">Information for the student.</Notice>
        <Notice tone="success" title="Saved">Your listing was sent for review.</Notice>
        <Notice tone="error" onDismiss={() => {}}>Sign-out could not be confirmed. Please retry.</Notice>
        <div className="actions"><Button onClick={() => setToast(true)}>Show toast</Button></div>
        {toast && <Toast tone="success" onDismiss={() => setToast(false)} autoDismissMs={6000}>Copied to clipboard.</Toast>}
      </section>

      <section aria-labelledby="g-dialog"><h2 id="g-dialog">Dialog</h2>
        <Button ref={opener} onClick={() => setOpen(true)}>Open dialog</Button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Remove this listing?" actions={<><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="danger" onClick={() => setOpen(false)}>Remove</Button></>}>
          Buyers will no longer see it. This cannot be undone.
        </Dialog>
      </section>

      <section aria-labelledby="g-states"><h2 id="g-states">EmptyState and ErrorState</h2>
        <EmptyState title="No listings yet" action={<Button variant="primary" href="/listings/new">Create listing</Button>}>Nothing has been posted here. Be the first to sell something.</EmptyState>
        <ErrorState title="Could not load listings" onRetry={() => {}} />
      </section>

      <section aria-labelledby="g-notfound"><h2 id="g-notfound">NotFound</h2>
        <NotFound authed={false} headingLevel={3} navigate={(event) => event.preventDefault()} />
      </section>
    </main>
  );
}

export default Gallery;
