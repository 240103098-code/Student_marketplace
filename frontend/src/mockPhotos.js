// Only the DEV mock module imports this asset namespace. No public/static bypass.
export const photoFixtures=[
 {id:1,title:"Graphing calculator, works perfectly",price:'38000.00',category_id:1,url:new URL('./mock-assets/listing-calculator.jpg',import.meta.url).href},
 {id:2,title:"Noise-cancelling over-ear headphones",price:'62000.00',category_id:1,url:new URL('./mock-assets/listing-headphones.jpg',import.meta.url).href},
 {id:3,title:"24-inch IPS monitor, 1080p",price:'45000.00',category_id:1,url:new URL('./mock-assets/listing-monitor.jpg',import.meta.url).href},
 {id:4,title:"Algorithms textbook bundle (4 books)",price:'12000.00',category_id:3,url:new URL('./mock-assets/listing-textbooks.jpg',import.meta.url).href},
 {id:5,title:"Winter down jacket, size M",price:'25000.00',category_id:2,url:new URL('./mock-assets/listing-jacket.jpg',import.meta.url).href},
 {id:6,title:"LED desk lamp with USB charging port",price:'6500.00',category_id:4,url:new URL('./mock-assets/listing-desklamp.jpg',import.meta.url).href}
];
export async function readLocalAsset(url){const response=await fetch(url);if(!response.ok)throw new Error('Demo photo unavailable.');return new Blob([await response.arrayBuffer()],{type:'image/jpeg'});}
