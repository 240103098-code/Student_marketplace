import React, { useEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from './Auth.jsx';
import { RecoveryRequestForm, ResetPasswordForm } from './RecoveryForms.jsx';
import { AdminListings,AdminListingDetail } from './AdminListings.jsx';
import { AdminUsers } from './AdminUsers.jsx';
import { AdminLanding } from './AdminLanding.jsx';
import { ListingDetail } from './ListingDetail.jsx';
import { Marketplace } from './Marketplace.jsx';
import { MyListings } from './MyListings.jsx';
import { EditListingForm } from './EditListingForm.jsx';
import { NewListingForm } from './NewListingForm.jsx';
import { AvatarControl } from './AvatarControl.jsx';
import { ProfileForm } from './ProfileForm.jsx';
import { PasswordForm } from './PasswordForm.jsx';
import { LoginForm } from './LoginForm.jsx';
import { RegistrationForm, VerificationForm } from './AccountForms.jsx';

const views = {
  '/': {
    title: 'Your campus marketplace',
    description: 'A simple place for students to discover useful things and connect with sellers. We are getting it ready for you.',
  },
  '/login': {
    title: 'Sign in',
    description: 'Sign in with your verified university account.',
  },
  '/register': {
    title: 'Create your account',
    description: 'Use your university email to create an account, then verify it with the code sent by email.',
  },
  '/verify': {
    title: 'Verify your university email',
    description: 'Enter your university email and the six-digit code from your inbox. You can edit the email or request a replacement.',
  },
  '/marketplace': {
    title: 'Marketplace',
    description: 'Browse approved listings from verified university students. Search or filter to find what you need.',
  },
};

views['/forgot-password'] = { title: 'Recover your password', description: 'Request a reset code with your university email. Only eligible verified accounts can receive one.' };
views['/reset-password'] = { title: 'Reset password', description: 'Enter your university email, recovery code, and a new password. Codes last ten minutes.' };

views['/listings/new'] = { title: 'Create a listing', description: 'Describe your item and optionally add photos. New listings wait for manual admin review before publication.' };

views['/admin']={title:'Administration',description:'Access is checked against your current university account permissions.'};
views['/admin/users']={title:'User review',description:'Review university accounts and manage student suspension.'};
views['/admin/listings']={title:'Listing review',description:'Inspect current listing states and remove inappropriate buyer-visible content.'};
const protectedPaths = ['/admin/listings','/admin/users','/admin', '/marketplace', '/profile', '/my-listings', '/account/password', '/listings/new'];
function editListingId(path) {
  const match=/^\/listings\/([1-9][0-9]{0,18})\/edit$/.exec(path);
  return match && BigInt(match[1])<=9223372036854775807n ? match[1] : null;
}
function detailListingId(path){const match=/^\/listings\/([1-9][0-9]{0,18})$/.exec(path);return match&&BigInt(match[1])<=9223372036854775807n?match[1]:null;}
function adminListingId(path){const match=/^\/admin\/listings\/([1-9][0-9]{0,18})$/.exec(path);return match&&BigInt(match[1])<=9223372036854775807n?match[1]:null;}
function protectedPath(path) { return protectedPaths.includes(path)||!!editListingId(path)||!!detailListingId(path)||!!adminListingId(path); }
export function safeReturnPath(path) { return protectedPath(path) ? path : '/marketplace'; }
views['/account/password'] = { title: 'Change password', description: 'Confirm your current password to set a new one. This signs out every session for your account.' };
views['/profile'] = { title: 'Profile', description: 'View and edit your name and optional external contact details. Your verified university email stays fixed.' };
views['/my-listings'] = { title: 'My Listings', description: 'Review your own listings and their actual publication or moderation state.' };

const navigation = [
  ['/', 'Home'],
  ['/marketplace', 'Marketplace'],
  ['/login', 'Sign in'],
  ['/register', 'Register'],
  ['/verify', 'Verify email'],
];

export function App() { return <AuthProvider><AppShell /></AuthProvider>; }

function AppShell() {
  const auth = useAuth();
  const [returnPath, setReturnPath] = useState('/marketplace');
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const logoutBusy = useRef(false);
  const [path, setPath] = useState(window.location.pathname);
  const heading = useRef(null);
  const previousPath = useRef(path);
  const [recovery, setRecovery] = useState({ email: '', cooldowns: {} });
  const [verification, setVerification] = useState({ email: '', cooldowns: {} });

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

  useEffect(() => {
    if (protectedPath(path) && auth.status === 'anonymous') {
      setReturnPath(safeReturnPath(path));
      window.history.replaceState(null, '', '/login');
      setPath('/login');
    }
  }, [path, auth.status]);

  useEffect(()=>{if(path==='/'&&auth.status==='authenticated'){window.history.replaceState(null,'','/marketplace');setPath('/marketplace');}},[path,auth.status]);

  async function signOut() {
    if (logoutBusy.current) return;
    logoutBusy.current = true; setLogoutPending(true); setLogoutError('');
    try { await auth.logout(); goTo('/login'); }
    catch { setLogoutError('Sign-out could not be confirmed. Your session may still be active. Please retry.'); }
    finally { logoutBusy.current = false; setLogoutPending(false); }
  }

  function navigate(event) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    goTo(event.currentTarget.getAttribute('href'));
  }

  function goTo(nextPath) {
    if (window.location.pathname !== nextPath) window.history.pushState(null, '', nextPath);
    setPath(nextPath);
  }

  const editId=editListingId(path),detailId=detailListingId(path),adminListing=adminListingId(path);
  const guarded = protectedPath(path) && auth.status !== 'authenticated';
  const view = guarded ? { title: 'Checking your session', description: 'Please wait while we confirm access.' } : editId ? { title: 'Edit listing', description: 'Change only price and description. Existing approval and publication stay unchanged.' } : adminListing ? {title:'Admin listing review',description:'Private review of listing content and retained records.'} : detailId ? {title:'Listing details',description:'Contact the seller directly to arrange your purchase.'} : views[path] || {
    title: 'Page not found',
    description: 'We could not find this page. Head back home to explore the preview.',
  };

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href={auth.status==='authenticated'?'/marketplace':'/'} onClick={navigate}>Student Marketplace</a>
          <nav aria-label="Main navigation">
            {navigation.filter(([href]) => auth.status !== 'authenticated' || !['/login', '/register', '/verify'].includes(href)).map(([href, label]) => (
              <a key={href} href={href==='/'&&auth.status==='authenticated'?'/marketplace':href} onClick={navigate} aria-current={path === href ? 'page' : undefined}>{label}</a>
            ))}
            {auth.status === 'authenticated' && <>
              {auth.user.is_admin&&<a href="/admin" onClick={navigate}>Admin</a>}
              <a href="/listings/new" onClick={navigate}>Create listing</a>
              <a href="/profile" onClick={navigate}>Profile</a>
              <a href="/my-listings" onClick={navigate}>My Listings</a>
              <a href="/account/password" onClick={navigate}>Change password</a>
              <button className="button secondary" onClick={signOut} disabled={logoutPending}>{logoutPending ? 'Signing out...' : 'Sign out'}</button>
            </>}
          </nav>
        </div>
      </header>
      <main id="main" className="main-content" tabIndex={-1}>
        <div className="preview-label">{['/register', '/verify'].includes(path) ? 'University accounts' : auth.status==='authenticated' ? 'University marketplace' : 'University community'}</div>
        <h1 ref={heading} tabIndex={-1}>{view.title}</h1>
        <p className="intro">{view.description}</p>
        {auth.message && <p role="status" className="form-feedback">{auth.message}</p>}
        {logoutError && <p role="alert" className="form-feedback error">{logoutError}</p>}
        {logoutPending && <p role="status">Confirming sign-out...</p>}
        {guarded && <p role="status">Checking your session...</p>}
        {path === '/admin/listings' && !guarded && <AdminListings navigate={navigate} />}
        {adminListing && !guarded && <AdminListingDetail listingId={adminListing} key={adminListing} navigate={navigate} />}
        {path === '/admin/users' && !guarded && <AdminUsers navigate={navigate} />}
        {path === '/admin' && !guarded && <AdminLanding navigate={navigate} />}
        {path === '/marketplace' && !guarded && <Marketplace navigate={navigate} />}
        {path === '/my-listings' && !guarded && <MyListings navigate={navigate} />}
        {detailId && !guarded && <ListingDetail listingId={detailId} key={detailId} navigate={navigate} />}
        {editId && !guarded && <EditListingForm listingId={editId} key={editId} />}
        {path === '/listings/new' && !guarded && <NewListingForm navigate={navigate} />}
        {path === '/profile' && !guarded && <><AvatarControl /><ProfileForm /></>}
        {path === '/forgot-password' && <RecoveryRequestForm initialEmail={recovery.email} cooldowns={recovery.cooldowns} navigate={navigate} onRequested={(email, deadline) => setRecovery(previous => ({ email, cooldowns: { ...previous.cooldowns, [email]: deadline } }))} />}
        {path === '/reset-password' && <ResetPasswordForm initialEmail={recovery.email} navigate={navigate} onReset={() => goTo('/login')} />}
        {path === '/account/password' && !guarded && <PasswordForm onChanged={() => goTo('/login')} />}
        {path === '/login' && <LoginForm navigate={navigate} onSignedIn={() => goTo(safeReturnPath(returnPath))} />}
        {path === '/register' && <RegistrationForm navigate={navigate} onRegistered={(email, deadline) => {
          setVerification(previous => ({ email, cooldowns: { ...previous.cooldowns, [email]: deadline } }));
          goTo('/verify');
        }} />}
        {path === '/verify' && <VerificationForm initialEmail={verification.email} cooldowns={verification.cooldowns} navigate={navigate} onCooldown={(email, deadline) => setVerification(previous => ({ email, cooldowns: { ...previous.cooldowns, [email]: deadline } }))} />}
        {path === '/' && (
          <div className="actions">
            <a className="button primary" href="/marketplace" onClick={navigate}>Explore marketplace</a>
            <a className="button secondary" href="/register" onClick={navigate}>Create an account</a>
          </div>
        )}
        {!views[path] && !editId && !detailId && !adminListing && <a className="button secondary" href="/" onClick={navigate}>Back to home</a>}
        <aside className="preview-note" aria-label="Preview information">
          <span className="note-dot" aria-hidden="true" />
          <p>Only verified university students can access approved marketplace listings. Negotiate, pay and arrange pickup directly with the seller.</p>
        </aside>
      </main>
      <footer className="site-footer">Student Marketplace <span aria-hidden="true">·</span> For your university community</footer>
    </>
  );
}
