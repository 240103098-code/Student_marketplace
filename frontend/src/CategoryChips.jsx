import React from 'react';
import {Button} from './ui/index.js';

/** "All" plus the server categories. Skeleton chips while loading; a retry notice on failure. */
export function CategoryChips({categories,error,value,onSelect,onRetry}){
 if(error)return <div className="catalog-chips-error"><p role="alert" className="form-feedback error">Categories could not be loaded.</p><Button onClick={onRetry}>Retry categories</Button></div>;
 if(!categories)return <div className="catalog-chips"><span className="catalog-chips__skeletons" aria-hidden="true">{[0,1,2,3,4,5].map(i=><span key={i} className="skeleton chip chip--skeleton"/>)}</span><p role="status" className="sr-only">Loading categories…</p></div>;
 const chip=(id,label)=><button key={id||'all'} type="button" className="chip" aria-pressed={String(value)===String(id)} onClick={()=>onSelect(String(id))}>{label}</button>;
 return <div className="catalog-chips" role="group" aria-label="Filter by category">{chip('', 'All')}{categories.map(c=>chip(c.id,c.label))}</div>;
}
