import React from 'react';
import { Button } from './Button.jsx';

/**
 * Plain-language failure state. Callers pass a fixed, human-written `message`; raw server text,
 * error objects and tokens must never be passed in.
 */
export function ErrorState({ title = 'Something went wrong', message = 'We could not load this right now. Check your connection and try again.', onRetry, retryLabel = 'Try again', headingLevel = 2 }) {
  const Heading = `h${headingLevel}`;
  return (
    <div className="state-card state-card--error" role="alert">
      <Heading>{title}</Heading>
      <p>{message}</p>
      {onRetry && <div className="state-card__actions"><Button variant="primary" onClick={onRetry}>{retryLabel}</Button></div>}
    </div>
  );
}
