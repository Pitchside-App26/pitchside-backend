/* ═══════════════════════════════════════════════════════════
   PHASE A — PART 1: Supabase init · Age gate · Auth
   ═══════════════════════════════════════════════════════════ */

/* ── Shared state ── */
var sbClient    = null;   // Supabase client instance
var authUser    = null;   // supabase auth user object
var userProfile = null;   // user_profiles row
var _onboarding = false;  // true while user is in onboarding — suppresses profile re-render

/* ─────────────────────────────────────────
   SUPABASE INITIALISATION
   Reads sb_url / sb_key from localStorage
   (set by the connection panel in Profile)
───────────────────────────────────────── */
function initSupabase() {
  // Hardcoded fallbacks for testing — remove before production
  const SUPABASE_URL = 'https://vmwcumegngppqojetfvv.supabase.co';
  const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZtd2N1bWVnbmdwcHFvamV0ZnZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3MjUxMzEsImV4cCI6MjA5MTMwMTEzMX0.H6KkZzjI_iShy6pr7AVCgWQi9TTzNL9qtkViL8dOw9I';

  var url = localStorage.getItem('sb_url') || SUPABASE_URL;
  var key = localStorage.getItem('sb_key') || SUPABASE_KEY;
  if (!url || !key) return;

  try {
    sbClient = window.supabase.createClient(url, key);
  } catch (e) {
    console.warn('Supabase init failed:', e);
    return;
  }

  // Listen for auth changes (tab switches, token refresh, etc.)
  sbClient.auth.onAuthStateChange(function(event, session) {
    authUser = session ? session.user : null;
    if (authUser) {
      if (!_onboarding) loadUserProfile(); // skip during onboarding flow
    } else {
      _onboarding = false;
      userProfile = null;
      updateBettingGates();
      updateProfileScreen();
    }
  });

  // Check existing session on load
  checkAuthState();
}

/* ─────────────────────────────────────────
   AGE GATE
   Checks localStorage for rundown_age_verified.
   If absent, injects DOB dropdowns into #ageGate
   and displays the overlay.
───────────────────────────────────────── */
function initAgeGate() {
  if (localStorage.getItem('rundown_age_verified') === '1') return;

  var gate = document.getElementById('ageGate');
  if (!gate) return;

  // Build DOB form and inject into gate
  var months = ['January','February','March','April','May','June',
                'July','August','September','October','November','December'];
  var curYear = new Date().getFullYear();

  var dayOpts  = '<option value="">Day</option>'   + Array.from({length:31}, function(_,i){ return '<option value="'+(i+1)+'">'+(i+1)+'</option>'; }).join('');
  var monOpts  = '<option value="">Month</option>' + months.map(function(m,i){ return '<option value="'+(i+1)+'">'+m+'</option>'; }).join('');
  var yearOpts = '<option value="">Year</option>'  + Array.from({length:100}, function(_,i){ var y=curYear-18-i; return '<option value="'+y+'">'+y+'</option>'; }).join('');

  var inputStyle = 'flex:1;padding:10px 8px;border:1.5px solid var(--rule-strong);border-radius:8px;font-family:var(--fm);font-size:13px;background:var(--card);color:var(--ink);outline:none;';

  gate.innerHTML =
    '<div style="font-family:var(--fd);font-size:22px;font-weight:800;color:var(--ink);margin-bottom:4px">The Run<em style="color:var(--live);font-style:italic">down</em></div>' +
    '<div style="font-family:var(--fm);font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:var(--ink5);margin-bottom:28px">Sports companion</div>' +
    '<div style="font-size:36px;margin-bottom:14px">🎟️</div>' +
    '<div style="font-family:var(--fd);font-size:24px;font-weight:800;color:var(--ink);line-height:1.2;margin-bottom:10px">Are you 18<br>or over?</div>' +
    '<div style="font-family:var(--fs);font-size:12px;color:var(--ink4);line-height:1.6;margin-bottom:22px;max-width:250px">This app contains betting content. Enter your date of birth to confirm you are 18 or over.</div>' +
    '<div style="font-family:var(--fm);font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--ink4);margin-bottom:8px;align-self:flex-start">Date of birth</div>' +
    '<div style="display:flex;gap:8px;margin-bottom:14px;width:100%">' +
      '<select id="ag-day"   style="'+inputStyle+'">'+dayOpts+'</select>' +
      '<select id="ag-month" style="'+inputStyle+'flex:1.6;">'+monOpts+'</select>' +
      '<select id="ag-year"  style="'+inputStyle+'flex:1.6;">'+yearOpts+'</select>' +
    '</div>' +
    '<div id="ag-error" style="display:none;font-family:var(--fs);font-size:12px;color:var(--live);margin-bottom:10px;text-align:center;width:100%"></div>' +
    '<button onclick="checkAgeGate()" style="width:100%;background:var(--ink);color:var(--parchment);padding:14px;border-radius:10px;font-family:var(--fs);font-size:14px;font-weight:700;border:none;cursor:pointer;margin-bottom:10px">Confirm age &amp; continue</button>' +
    '<button onclick="ageGateFail()" style="width:100%;background:transparent;color:var(--ink4);padding:13px;border-radius:10px;font-family:var(--fs);font-size:13px;font-weight:600;border:1.5px solid var(--rule-strong);cursor:pointer">I am under 18</button>' +
    '<div style="font-family:var(--fm);font-size:8px;color:var(--ink5);margin-top:20px;line-height:1.6;text-align:center">18+ · BeGambleAware.org · GamStop.co.uk</div>';

  gate.style.display = 'flex';
}

function checkAgeGate() {
  var d = parseInt(document.getElementById('ag-day').value,   10);
  var m = parseInt(document.getElementById('ag-month').value, 10);
  var y = parseInt(document.getElementById('ag-year').value,  10);
  var errEl = document.getElementById('ag-error');

  if (!d || !m || !y) {
    errEl.textContent = 'Please select your full date of birth.';
    errEl.style.display = 'block';
    return;
  }

  var dob  = new Date(y, m - 1, d);
  var now  = new Date();
  var age  = now.getFullYear() - dob.getFullYear();
  var had  = now >= new Date(now.getFullYear(), dob.getMonth(), dob.getDate());
  if (!had) age--;

  if (age < 18) {
    errEl.textContent = 'You must be 18 or over to use this app.';
    errEl.style.display = 'block';
    return;
  }

  ageGatePass();
}

function ageGatePass() {
  localStorage.setItem('rundown_age_verified', '1');
  var gate = document.getElementById('ageGate');
  if (gate) gate.style.display = 'none';
  // Registration is mandatory — go straight to register screen
  showAuthScreen('auth-register');
}

function ageGateFail() {
  document.body.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#1a1714;font-family:Instrument Sans,sans-serif;color:rgba(255,255,255,0.5);text-align:center;padding:40px">' +
    '<div><div style="font-size:40px;margin-bottom:16px">🚫</div>' +
    '<div style="font-size:16px">This app is for users aged 18 and over only.</div>' +
    '<div style="font-size:12px;margin-top:8px">BeGambleAware.org · GamStop.co.uk</div></div></div>';
}

/* ─────────────────────────────────────────
   AUTH STATE MANAGEMENT
───────────────────────────────────────── */
function checkAuthState() {
  if (!sbClient) return;
  sbClient.auth.getSession().then(function(result) {
    var session = result.data.session;
    authUser = session ? session.user : null;
    if (authUser) {
      loadUserProfile();
    } else {
      updateBettingGates();
      updateProfileScreen();
    }
  });
}

function loadUserProfile() {
  if (!sbClient || !authUser) return;
  sbClient
    .from('user_profiles')
    .select('*')
    .eq('id', authUser.id)
    .single()
    .then(function(result) {
      if (result.data) {
        userProfile = result.data;
      } else {
        // Row missing — create it (e.g. OAuth sign-in without registration flow)
        sbClient.from('user_profiles').insert({
          id: authUser.id,
          favourite_teams:    [],
          bookmaker_accounts: [],
          trust_tier:         'New Fan',
          gdpr_consent:       false
        }).then(function() {
          userProfile = { id: authUser.id, favourite_teams: [], bookmaker_accounts: [], trust_tier: 'New Fan', gdpr_consent: false };
          updateBettingGates();
          updateProfileScreen();
        });
        return;
      }
      updateBettingGates();
      updateProfileScreen();
    });
}

function updateBettingGates() {
  // Screens that require auth: n9 (AI Bet), n10 (Bet Builder), n11 (In-Play Tracker)
  var gatedIds = ['n9', 'n10', 'n11'];
  var loggedIn = !!authUser;
  gatedIds.forEach(function(id) {
    var screen = document.getElementById(id);
    if (!screen) return;
    var gate = screen.querySelector('.auth-gate');
    if (!gate) return;
    if (loggedIn) {
      gate.classList.remove('show');
    } else {
      gate.classList.add('show');
    }
  });
}

function updateProfileScreen() {
  var container = document.getElementById('profile-dynamic');
  if (!container) return;

  if (!sbClient) {
    // No Supabase connected — show connection card
    container.innerHTML =
      '<div style="overflow-y:auto;height:100%;padding-bottom:10px">' +
      '<div class="sb-connect-card">' +
        '<div class="sb-connect-title">Connect Supabase</div>' +
        '<div class="sb-connect-sub">Enter your project URL and anon key. Find these in your Supabase dashboard under Project Settings → API.</div>' +
        '<input class="sb-connect-input" id="sb-url-input" type="url" placeholder="https://xxxx.supabase.co" autocomplete="off"/>' +
        '<input class="sb-connect-input" id="sb-key-input" type="text" placeholder="anon public key" autocomplete="off"/>' +
        '<button class="sb-connect-btn" onclick="saveSupabaseCredentials()">Connect</button>' +
      '</div></div>';
    return;
  }

  if (!authUser) {
    // Connected but not logged in
    container.innerHTML =
      '<div class="profile-cta-wrap">' +
        '<div class="profile-cta-icon">👤</div>' +
        '<div class="profile-cta-title">Your account</div>' +
        '<div class="profile-cta-sub">Sign in to see your favourite teams, bookmaker accounts and betting history.</div>' +
        '<button class="profile-cta-btn primary" onclick="showAuthScreen(\'auth-login\')">Sign In</button>' +
        '<button class="profile-cta-btn secondary" onclick="showAuthScreen(\'auth-register\')">Create Account</button>' +
      '</div>';
    return;
  }

  // Logged in — build full profile view
  var p = userProfile || {};
  var teams = (p.favourite_teams || []);
  var bookies = (p.bookmaker_accounts || []);
  var tier = p.trust_tier || 'New Fan';
  var tierIcon = tier === 'New Fan' ? '🌱' : tier === 'Regular Fan' ? '⭐' : '🔴';
  var initials = (authUser.email || 'U').substring(0,2).toUpperCase();

  var teamRows = teams.length
    ? teams.map(function(t){ return '<div class="profile-row"><div class="profile-row-icon" style="background:var(--live-bg)">⚽</div><div class="profile-row-label">'+t+'</div><div class="profile-row-arrow">›</div></div>'; }).join('')
    : '<div style="padding:12px 16px;font-family:var(--fs);font-size:12px;color:var(--ink4)">No teams selected yet. <span style="color:var(--ink);font-weight:700;cursor:pointer" onclick="showAuthScreen(\'auth-onboard1a\')">Add teams →</span></div>';

  var bookieRows = bookies.length
    ? bookies.map(function(b){ return '<div class="bookie-row"><div class="bookie-name">'+b+'</div><div class="bookie-toggle on"><div class="bookie-toggle-dot"></div></div></div>'; }).join('')
    : '<div style="padding:12px 16px;font-family:var(--fs);font-size:12px;color:var(--ink4)">No bookmakers added yet.</div>';

  container.innerHTML =
    '<div style="overflow-y:auto;height:100%">' +
      '<div class="profile-hero">' +
        '<div class="profile-avatar">'+initials+'</div>' +
        '<div class="trust-badge-hero"><span class="tb-icon">'+tierIcon+'</span><span class="tb-label">'+tier.toUpperCase()+'</span></div>' +
        '<div class="profile-name">'+(authUser.email || '')+'</div>' +
        '<div class="profile-meta">Member · '+tier+'</div>' +
        '<div class="profile-tabs">' +
          '<div class="profile-tab on">Overview</div>' +
          '<div class="profile-tab">Bets</div>' +
          '<div class="profile-tab">Reports</div>' +
          '<div class="profile-tab">Settings</div>' +
        '</div>' +
      '</div>' +
      '<div class="profile-section-header" style="margin-top:12px">Favourite Teams</div>' +
      teamRows +
      '<div class="profile-section-header" style="margin-top:4px">Bookmaker Accounts</div>' +
      bookieRows +
      '<div style="padding:10px 16px 4px"></div>' +
      '<button class="profile-signout-btn" onclick="doSignOut()">Sign Out</button>' +
      '<div style="height:14px"></div>' +
    '</div>';
}

/* ─────────────────────────────────────────
   SUPABASE CREDENTIALS (connection card)
───────────────────────────────────────── */
function saveSupabaseCredentials() {
  var url = (document.getElementById('sb-url-input') || {}).value || '';
  var key = (document.getElementById('sb-key-input') || {}).value || '';
  if (!url || !key) { showToast('Please enter both URL and anon key', 'error'); return; }
  localStorage.setItem('sb_url', url.trim());
  localStorage.setItem('sb_key', key.trim());
  initSupabase();
  updateProfileScreen();
  showToast('Connected to Supabase', 'success');
}

/* ─────────────────────────────────────────
   REGISTRATION
───────────────────────────────────────── */
function doRegister() {
  var errEl = document.getElementById('reg-error');
  function setErr(msg) {
    if (errEl) { errEl.textContent = msg; errEl.classList.add('show'); }
    else showToast(msg, 'error');
  }

  if (!sbClient) { setErr('Connection error — please refresh and try again'); return; }

  var email = (document.getElementById('reg-email') || {}).value || '';
  var pw    = (document.getElementById('reg-pw')    || {}).value || '';
  var pw2   = (document.getElementById('reg-pw2')   || {}).value || '';
  var gdpr  = (document.getElementById('reg-gdpr')  || {}).checked;

  email = email.trim();

  if (!email || !pw || !pw2) { setErr('Please fill in all fields.'); return; }
  if (pw !== pw2)             { setErr('Passwords do not match.'); return; }
  if (pw.length < 6)          { setErr('Password must be at least 6 characters.'); return; }
  if (!gdpr)                  { setErr('You must agree to the Privacy Policy to continue.'); return; }
  if (errEl) errEl.classList.remove('show');

  var btn = document.getElementById('reg-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Creating account…'; }

  sbClient.auth.signUp({ email: email, password: pw }).then(function(result) {
    if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label || 'Create Account'; }
    if (result.error) { setErr(result.error.message); return; }

    authUser = result.data.user;
    _onboarding = true; // suppress onAuthStateChange → updateProfileScreen during onboarding

    // Create user_profiles row
    var now = new Date().toISOString();
    sbClient.from('user_profiles').insert({
      id:                 authUser.id,
      favourite_teams:    [],
      bookmaker_accounts: [],
      trust_tier:         'New Fan',
      gdpr_consent:       true,
      gdpr_consent_at:    now
    }).then(function(insResult) {
      if (insResult.error) {
        // Row may already exist (e.g. re-registration) — log but don't block
        console.warn('user_profiles insert:', insResult.error.message);
      }
      userProfile = { id: authUser.id, favourite_teams: [], bookmaker_accounts: [], trust_tier: 'New Fan', gdpr_consent: true };
      showToast('Account created!', 'success');
      // Go directly to onboarding — do NOT call hideAuthScreens() first
      // (that would trigger goTo() and show the profile screen)
      showAuthScreen('auth-onboard1a');
      if (typeof renderMyClubList === 'function') renderMyClubList('');
    });
  });
}

/* ─────────────────────────────────────────
   LOGIN
───────────────────────────────────────── */
function doLogin() {
  if (!sbClient) { showToast('Supabase not connected', 'error'); return; }

  var email = (document.getElementById('login-email') || {}).value || '';
  var pw    = (document.getElementById('login-pw')    || {}).value || '';
  var errEl = document.getElementById('login-error');
  email = email.trim();

  function setErr(msg) {
    if (errEl) { errEl.textContent = msg; errEl.classList.add('show'); }
    else showToast(msg, 'error');
  }

  if (!email || !pw) { setErr('Please enter your email and password.'); return; }
  if (errEl) errEl.classList.remove('show');

  var btn = document.getElementById('login-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Signing in…'; }

  sbClient.auth.signInWithPassword({ email: email, password: pw }).then(function(result) {
    if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label || 'Sign In'; }
    if (result.error) { setErr(result.error.message); return; }

    authUser = result.data.user;
    loadUserProfile();
    showToast('Welcome back!', 'success');
    hideAuthScreens();
    // Return to profile screen
    if (typeof goTo === 'function') goTo(13);
  });
}

/* ─────────────────────────────────────────
   SIGN OUT
───────────────────────────────────────── */
function doSignOut() {
  if (!sbClient) return;
  sbClient.auth.signOut().then(function() {
    authUser    = null;
    userProfile = null;
    updateBettingGates();
    updateProfileScreen();
    if (typeof goTo === 'function') goTo(0);
    showToast('Signed out', 'info');
  });
}

/* ─────────────────────────────────────────
   AUTH SCREEN NAVIGATION HELPERS
───────────────────────────────────────── */
var _prevScreenIdx = 0; // remembers where to return after auth

function showAuthScreen(screenId) {
  // Store current position so we can return
  if (typeof cur !== 'undefined') _prevScreenIdx = cur;

  // Expand phone to full viewport and hide shell chrome
  document.body.classList.add('auth-mode');

  // Hide all .screen divs and clear any inline display overrides
  document.querySelectorAll('.screen').forEach(function(s) {
    s.classList.remove('on');
    s.style.display = '';
  });

  var target = document.getElementById(screenId);
  if (target) {
    target.classList.add('on');
    var flexScreens = ['auth-onboard1a','auth-onboard1b','auth-onboard1c','auth-onboard2'];
    if (flexScreens.indexOf(screenId) !== -1) {
      target.style.display       = 'flex';
      target.style.flexDirection = 'column';
    } else {
      target.style.display       = 'block';
      target.style.flexDirection = '';
    }
  }

  // Populate My Club screen whenever shown
  if (screenId === 'auth-onboard1a') {
    if (typeof renderLeaguePanel === 'function') renderLeaguePanel();
    if (typeof renderMyClubList  === 'function') renderMyClubList('');
  }

  // Show/hide Supabase warning on login screen
  var noSbWarn = document.getElementById('login-no-sb');
  if (noSbWarn) noSbWarn.style.display = (!sbClient && screenId === 'auth-login') ? 'block' : 'none';
}

function hideAuthScreens() {
  _onboarding = false;

  // Restore phone shell chrome
  document.body.classList.remove('auth-mode');

  var authIds = ['auth-login','auth-register',
                 'auth-onboard1a','auth-onboard1b','auth-onboard1c','auth-onboard2'];
  authIds.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) { el.classList.remove('on'); el.style.display = ''; }
  });

  // Restore previous screen — use goTo only when returning to app, not mid-onboarding
  if (typeof goTo === 'function') goTo(_prevScreenIdx);
}

// Navigate by screen ID — bridges auth screens with the existing goTo() system
function goToScreen(screenId) {
  var authIds = ['auth-login','auth-register',
                 'auth-onboard1a','auth-onboard1b','auth-onboard1c','auth-onboard2'];
  if (authIds.indexOf(screenId) !== -1) {
    showAuthScreen(screenId);
    return;
  }
  // Named app screens
  var map = { 'n0':0,'n1':1,'n2':2,'n3':3,'n4':4,'n5':5,'n6':6,'n7':7,'n8':8,'n9':9,'n10':10,'n11':11,'n12':12,'n13':13 };
  if (map[screenId] !== undefined && typeof goTo === 'function') {
    hideAuthScreens();
    goTo(map[screenId]);
  }
}

/* ─────────────────────────────────────────
   TOAST UTILITY
   (safe to call before DOM is ready —
    will no-op if #toast doesn't exist yet)
───────────────────────────────────────── */
function showToast(msg, type) {
  var el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'toast show ' + (type || 'info');
  clearTimeout(el._t);
  el._t = setTimeout(function(){ el.classList.remove('show'); }, 3200);
}
