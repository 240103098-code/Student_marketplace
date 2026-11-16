import React from 'react';

/** Price-tag sticker. Currency is KZT. Pass `decorative` when the price is repeated in nearby text. */
export function PriceTag({ amount, currency = 'KZT', decorative = false }) {
  return (
    <span className="price-tag" aria-hidden={decorative ? true : undefined}>
      <span>{amount}</span>
      <span className="price-tag__currency">{currency}</span>
    </span>
  );
}
