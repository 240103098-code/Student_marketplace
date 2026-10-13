export function listingPrice(value) {
  if (!/^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value)) return null;
  const [whole,raw='']=value.split('.');
  const meaningful=raw.replace(/0+$/,'');
  if(meaningful.length>2 || whole.length>10 || (whole.length===10 && whole>'1000000000') || (whole==='1000000000' && /[1-9]/.test(raw))) return null;
  return `${whole}.${meaningful.padEnd(2,'0')}`;
}
