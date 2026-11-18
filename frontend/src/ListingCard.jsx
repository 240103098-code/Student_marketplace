import React from 'react';
import {Photo} from './Photo.jsx';
import {PriceTag,Skeleton} from './ui/index.js';

const MAX_STAGGER=8;
const dateFormat={day:'numeric',month:'short',year:'numeric'};
export function categoryLabel(categories,categoryError,id){
 return categories?.find(c=>c.id===id)?.label||(categoryError?'Category unavailable':'Category loading');
}
/** Photo-first catalog card. One link (the title) is stretched over the whole card. */
export function ListingCard({card,index,categories,categoryError,navigate}){
 return <li className="catalog-card" style={{'--i':Math.min(index,MAX_STAGGER)}}>
  <div className="catalog-card__media">
   {card.main_photo?<Photo key={card.main_photo.url} photo={card.main_photo} alt={card.title}/>:<><svg className="catalog-card__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M4 18l5-5 3 3 3-4 5 6"/></svg><p className="photo-state photo-state--none">No photo.</p></>}
  </div>
  <div className="catalog-card__body">
   <p className="catalog-card__price"><PriceTag amount={card.price} currency={card.currency} decorative/><span className="sr-only">{`${card.price} ${card.currency}`}</span></p>
   <h2 className="catalog-card__title"><a className="catalog-card__link" href={`/listings/${card.id}`} onClick={navigate} title={card.title}>{card.title}</a></h2>
   <p className="catalog-card__meta">{categoryLabel(categories,categoryError,card.category_id)} · {card.condition==='new'?'New':'Used'} · <time dateTime={card.published_at}>{new Date(card.published_at).toLocaleDateString(undefined,dateFormat)}</time></p>
  </div>
 </li>;
}
/** Same boxes as ListingCard (same CSS classes, fixed line heights) so swapping causes no layout shift. */
export function CatalogSkeleton(){
 return <div className="catalog-card catalog-card--skeleton" aria-hidden="true">
  <div className="catalog-card__media"><span className="skeleton skeleton--block catalog-card__fill"/></div>
  <div className="catalog-card__body">
   <p className="catalog-card__price"><span className="skeleton catalog-skel-price"/></p>
   <div className="catalog-card__title"><Skeleton shape="line" lines={2}/></div>
   <p className="catalog-card__meta"><span className="skeleton catalog-skel-meta"/></p>
  </div>
 </div>;
}
