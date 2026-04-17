// ── NAV-1 — 5-tab bottom navigation ─────────────────────

var NAV_TAB_MAP = {
  home:     [0, 1, 2, 3],
  matches:  [0],
  matchday: [5, 6, 7, 8],
  bets:     [12, 9, 10, 11],
  profile:  [13]
};

var NAV_TAB_DEFAULT = {
  home:     0,
  matches:  0,
  matchday: 5,
  bets:     12,
  profile:  13
};

var currentNavTab = 'home';

/* ── Visibility helpers ─────────────────────────────── */
var AUTH_SCREEN_IDS = [
  'auth-login', 'auth-register',
  'auth-onboard1a', 'auth-onboard1b', 'auth-onboard1c',
  'auth-onboard2'
];

function navBarShow() {
  var el = document.querySelector('.rundown-nav');
  if (el) el.style.display = 'flex';
}

function navBarHide() {
  var el = document.querySelector('.rundown-nav');
  if (el) el.style.display = 'none';
}

/* ── Core nav functions ─────────────────────────────── */
function navGo(tabName) {
  if (!NAV_TAB_MAP[tabName]) return;
  currentNavTab = tabName;
  var targetScreen = NAV_TAB_DEFAULT[tabName];
  goTo(targetScreen);
  updateNavActiveState();
  navBarShow();
}

function updateNavActiveState() {
  document.querySelectorAll('.rundown-nav-tab').forEach(function(el) {
    el.classList.toggle('active', el.dataset.tab === currentNavTab);
  });
}

function syncNavToScreen(screenIdx) {
  if (screenIdx === 13) {
    currentNavTab = 'profile';
    updateNavActiveState();
    return;
  }
  if ([9, 10, 11, 12].indexOf(screenIdx) !== -1) {
    currentNavTab = 'bets';
    updateNavActiveState();
    return;
  }
  if ([5, 6, 7, 8].indexOf(screenIdx) !== -1) {
    currentNavTab = 'matchday';
    updateNavActiveState();
    return;
  }
  // n0-n3: keep current tab (Home or Matches)
}

/* ── Wrap goTo to sync nav state ────────────────────── */
var _originalGoTo = null;

function _installGoToWrapper() {
  if (typeof goTo !== 'function') return;
  _originalGoTo = goTo;
  goTo = function(idx) {
    _originalGoTo(idx);
    syncNavToScreen(idx);
    /* Any goTo call means we're past auth — show the nav bar */
    navBarShow();
  };
}

/* ── Wrap showAuthScreen to hide nav during auth ────── */
function _installAuthWrapper() {
  if (typeof showAuthScreen !== 'function') return;
  var _origShowAuth = showAuthScreen;
  showAuthScreen = function(screenId) {
    _origShowAuth(screenId);
    navBarHide();
  };
}

/* ── Init ───────────────────────────────────────────── */
window.addEventListener('load', function() {
  /* Nav bar hidden by default — shown once user passes auth */
  navBarHide();

  setTimeout(function() {
    _installGoToWrapper();
    _installAuthWrapper();
    updateNavActiveState();
  }, 300);
});
