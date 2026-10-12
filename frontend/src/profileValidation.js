export function validContactUrl(value) {
  if (Array.from(value).length > 2048 || /[\s\u0000-\u001f\u007f]/u.test(value) || !/^https:\/\//i.test(value)) return false;
  try {
    const authority = value.match(/^https:\/\/([^/?#]+)/i)?.[1];
    if (!authority || authority.includes('%') || authority.includes('@') || authority.includes('\\')) return false;
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || !url.hostname || url.port === '0') return false;
    if (url.hostname.startsWith('[')) return true; // URL validates bracketed IPv6.
    const hostname = url.hostname.replace(/\.$/, '');
    return hostname.length <= 253 && hostname.split('.').every(label => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label));
  } catch { return false; }
}

export function profileChangeError(changes) {
  if ('name' in changes && (!changes.name || Array.from(changes.name).length > 100)) return 'Name must contain 1–100 characters after trimming.';
  if (changes.phone !== undefined && changes.phone !== null && !/^\+[0-9]{7,15}$/.test(changes.phone)) return 'Use + followed by 7–15 digits for your phone.';
  if (changes.telegram_username !== undefined && changes.telegram_username !== null && !/^[A-Za-z0-9_]{5,32}$/.test(changes.telegram_username)) return 'Telegram username must contain 5–32 letters, digits, or underscores.';
  if (changes.external_contact_url !== undefined && changes.external_contact_url !== null && !validContactUrl(changes.external_contact_url)) return 'Use an HTTPS contact URL up to 2048 characters with a valid host and no login details or spaces.';
  return '';
}
