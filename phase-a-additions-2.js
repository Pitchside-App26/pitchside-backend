/* ═══════════════════════════════════════════════════════════
   PHASE A — PART 2 (revised): Three-tier team onboarding
   + Bookmakers + window load handler
   ═══════════════════════════════════════════════════════════ */

/* ── Onboarding state ── */
var selectedMyClub    = '';   // single string — auth-onboard1a
var goesToMatches     = null; // boolean — auth-onboard1b Yes/No
var selectedWatchLive = [];   // up to 5 — auth-onboard1b
var selectedFollow    = [];   // up to 10 — auth-onboard1c
var selectedBookmakers = [];  // auth-onboard2

/* ─────────────────────────────────────────
   ALL_TEAMS
   NOTE: Reflects 2024/25 season.
   Review every summer — promotion/relegation
   changes memberships annually.
   Long-term: replace with API-Football /teams.
───────────────────────────────────────── */
var ALL_TEAMS = {
  'PREMIER LEAGUE': [
    'Arsenal','Aston Villa','Bournemouth','Brentford','Brighton',
    'Chelsea','Crystal Palace','Everton','Fulham','Ipswich Town',
    'Leicester City','Liverpool','Manchester City','Manchester United',
    'Newcastle United','Nottingham Forest','Southampton',
    'Tottenham Hotspur','West Ham United','Wolverhampton Wanderers'
  ],
  'CHAMPIONSHIP': [
    'Birmingham City','Blackburn Rovers','Blackpool','Bristol City',
    'Burnley','Cardiff City','Coventry City','Derby County','Hull City',
    'Leeds United','Luton Town','Middlesbrough','Millwall','Norwich City',
    'Oxford United','Plymouth Argyle','Portsmouth','Preston North End',
    'Queens Park Rangers','Sheffield United','Sheffield Wednesday',
    'Stoke City','Sunderland','Swansea City','Watford','West Bromwich Albion'
  ],
  'LEAGUE ONE': [
    'Barnsley','Birmingham City','Bolton Wanderers','Bristol Rovers',
    'Burton Albion','Cambridge United','Charlton Athletic','Crawley Town',
    'Exeter City','Leyton Orient','Lincoln City','Mansfield Town',
    'MK Dons','Northampton Town','Peterborough United','Reading',
    'Rotherham United','Shrewsbury Town','Stevenage','Stockport County',
    'Wigan Athletic','Wrexham'
  ],
  'LEAGUE TWO': [
    'AFC Wimbledon','Barrow','Bradford City','Bromley','Carlisle United',
    'Chesterfield','Colchester United','Crewe Alexandra','Doncaster Rovers',
    'Fleetwood Town','Gillingham','Grimsby Town','Harrogate Town',
    'Morecambe','Newport County','Notts County','Port Vale','Salford City',
    'Swindon Town','Tranmere Rovers','Walsall','Accrington Stanley'
  ],
  'SCOTTISH PREMIERSHIP': [
    'Aberdeen','Celtic','Dundee','Dundee United','Falkirk',
    'Heart of Midlothian','Hibernian','Kilmarnock','Motherwell',
    'Rangers','Ross County','St Johnstone','St Mirren'
  ],
  'SCOTTISH CHAMPIONSHIP': [
    'Airdrieonians','Ayr United','Dunfermline Athletic',
    'Hamilton Academical','Inverness CT','Livingston','Morton',
    'Partick Thistle',"Queen's Park",'Raith Rovers'
  ],
  'SCOTTISH LEAGUE ONE': [
    'Alloa Athletic','Arbroath','Cove Rangers','Dumbarton','East Fife',
    'Kelty Hearts','Montrose','Peterhead','Stenhousemuir','Stirling Albion'
  ],
  'SCOTTISH LEAGUE TWO': [
    'Annan Athletic','Bonnyrigg Rose','Clyde','Edinburgh City','Elgin City',
    'Forfar Athletic','Queen of the South','Spartans','Stranraer'
  ]
};

/* Helper: find which league a team belongs to */
function leagueOf(team) {
  var found = '';
  Object.keys(ALL_TEAMS).forEach(function(lg) {
    if (ALL_TEAMS[lg].indexOf(team) !== -1) found = lg;
  });
  return found;
}

/* Helper: safe HTML render of a team row */
function teamRow(team, isSelected, isLocked, onclick) {
  var sel  = isSelected || isLocked;
  var icon = isLocked ? '🔒' : (isSelected ? '✓' : '');
  return '<div class="ob-team-row' + (sel ? ' selected' : '') + '"' +
    (isLocked ? '' : ' onclick="' + onclick + '"') + '>' +
    '<span class="ob-team-name">' + team + '</span>' +
    '<span class="ob-check">' + icon + '</span>' +
    '</div>';
}

/* ─────────────────────────────────────────
   ONBOARDING 1a — MY CLUB (single, mandatory)
───────────────────────────────────────── */
function renderMyClubList(filter) {
  var list = document.getElementById('ob1a-list');
  if (!list) return;
  var q = (filter || '').toLowerCase().trim();
  var html = '';
  var any = false;
  Object.keys(ALL_TEAMS).forEach(function(lg) {
    var teams = ALL_TEAMS[lg].filter(function(t) {
      return !q || t.toLowerCase().indexOf(q) !== -1;
    });
    if (!teams.length) return;
    any = true;
    html += '<div class="ob-league-hdr">' + lg + '</div>';
    teams.forEach(function(team) {
      var sel = selectedMyClub === team;
      html += teamRow(team, sel, false,
        'selectMyClub(\'' + team.replace(/'/g, "\\'") + '\')');
    });
  });
  if (!any) html = '<div class="ob-empty">No teams match "' + filter + '"</div>';
  list.innerHTML = html;
  updateMyClubCounter();
}

function filterMyClub(val) { renderMyClubList(val); }

function selectMyClub(team) {
  selectedMyClub = team;
  var searchEl = document.getElementById('ob1a-search');
  renderMyClubList(searchEl ? searchEl.value : '');
}

function updateMyClubCounter() {
  var el = document.getElementById('ob1a-counter');
  if (el) el.textContent = selectedMyClub ? selectedMyClub : 'No club selected';
  var btn = document.getElementById('ob1a-continue');
  if (btn) {
    btn.disabled = !selectedMyClub;
    btn.textContent = selectedMyClub
      ? 'Continue with ' + selectedMyClub + ' →'
      : 'Select your club to continue →';
  }
}

function submitMyClub() {
  if (!selectedMyClub) { showToast('Please select your club first', 'error'); return; }
  // Pre-seed follow list with My Club
  if (selectedFollow.indexOf(selectedMyClub) === -1) selectedFollow.unshift(selectedMyClub);
  // Pre-seed watch live with My Club
  if (selectedWatchLive.indexOf(selectedMyClub) === -1) selectedWatchLive.unshift(selectedMyClub);
  showAuthScreen('auth-onboard1b');
  renderWatchLiveList('');
}

/* ─────────────────────────────────────────
   ONBOARDING 1b — WATCH LIVE (up to 5, My Club locked)
───────────────────────────────────────── */
function answerGoesToMatches(yes) {
  goesToMatches = yes;
  // Highlight active button
  var yBtn = document.getElementById('ob1b-yes');
  var nBtn = document.getElementById('ob1b-no');
  var activeStyle = 'background:var(--ink);color:var(--parchment);border-color:var(--ink);';
  var idleStyle   = 'background:var(--card);color:var(--ink);border-color:var(--rule-strong);';
  if (yBtn) yBtn.setAttribute('style',
    'flex:1;padding:12px;border-radius:10px;font-family:var(--fs);font-size:14px;font-weight:700;border:1.5px solid;cursor:pointer;' +
    (yes ? activeStyle : idleStyle));
  if (nBtn) nBtn.setAttribute('style',
    'flex:1;padding:12px;border-radius:10px;font-family:var(--fs);font-size:14px;font-weight:700;border:1.5px solid;cursor:pointer;' +
    (!yes ? activeStyle : idleStyle));

  if (!yes) {
    // Skip straight to 1c — no live teams to pick
    selectedWatchLive = [selectedMyClub];
    showAuthScreen('auth-onboard1c');
    renderFollowList('');
    return;
  }
  // Show team picker
  var teamsEl  = document.getElementById('ob1b-teams');
  var footerEl = document.getElementById('ob1b-footer');
  if (teamsEl)  teamsEl.style.display  = 'flex';
  if (footerEl) footerEl.style.display = '';
  renderWatchLiveList('');
}

function renderWatchLiveList(filter) {
  var list = document.getElementById('ob1b-list');
  if (!list) return;
  var q = (filter || '').toLowerCase().trim();
  var html = '';
  var any = false;
  Object.keys(ALL_TEAMS).forEach(function(lg) {
    var teams = ALL_TEAMS[lg].filter(function(t) {
      return !q || t.toLowerCase().indexOf(q) !== -1;
    });
    if (!teams.length) return;
    any = true;
    html += '<div class="ob-league-hdr">' + lg + '</div>';
    teams.forEach(function(team) {
      var locked = team === selectedMyClub;
      var sel    = selectedWatchLive.indexOf(team) !== -1;
      html += teamRow(team, sel, locked,
        'toggleWatchLiveTeam(\'' + team.replace(/'/g, "\\'") + '\')');
    });
  });
  if (!any) html = '<div class="ob-empty">No teams match "' + filter + '"</div>';
  list.innerHTML = html;
  updateWatchLiveCounter();
}

function filterWatchLive(val) { renderWatchLiveList(val); }

function toggleWatchLiveTeam(team) {
  if (team === selectedMyClub) { showToast('Your club is always included', 'info'); return; }
  var idx = selectedWatchLive.indexOf(team);
  if (idx !== -1) {
    selectedWatchLive.splice(idx, 1);
  } else {
    if (selectedWatchLive.length >= 5) { showToast('Maximum 5 teams — remove one first', 'error'); return; }
    selectedWatchLive.push(team);
  }
  var searchEl = document.getElementById('ob1b-search');
  renderWatchLiveList(searchEl ? searchEl.value : '');
}

function updateWatchLiveCounter() {
  var el = document.getElementById('ob1b-counter');
  if (el) {
    var n = selectedWatchLive.length;
    el.textContent = n + ' of 5 selected';
    el.className = 'ob-counter' + (n >= 5 ? ' full' : '');
  }
}

function submitWatchLive() {
  // Merge watch-live into follow list
  selectedWatchLive.forEach(function(t) {
    if (selectedFollow.indexOf(t) === -1) selectedFollow.push(t);
  });
  showAuthScreen('auth-onboard1c');
  renderFollowList('');
}

/* ─────────────────────────────────────────
   ONBOARDING 1c — FOLLOW TEAMS (up to 10)
───────────────────────────────────────── */
function renderFollowList(filter) {
  var list = document.getElementById('ob1c-list');
  if (!list) return;
  var q = (filter || '').toLowerCase().trim();

  // Build ordered league list: My Club's league first, then rest
  var myLeague = leagueOf(selectedMyClub);
  var leagues  = Object.keys(ALL_TEAMS);
  if (myLeague) {
    leagues = [myLeague].concat(leagues.filter(function(l) { return l !== myLeague; }));
  }

  var lockedTeams = [selectedMyClub].concat(
    selectedWatchLive.filter(function(t) { return t !== selectedMyClub; })
  );

  var html = '';
  var any  = false;
  leagues.forEach(function(lg) {
    var teams = ALL_TEAMS[lg].filter(function(t) {
      return !q || t.toLowerCase().indexOf(q) !== -1;
    });
    if (!teams.length) return;
    any = true;
    html += '<div class="ob-league-hdr">' + lg + (lg === myLeague ? ' ★' : '') + '</div>';
    teams.forEach(function(team) {
      var locked = lockedTeams.indexOf(team) !== -1;
      var sel    = selectedFollow.indexOf(team) !== -1;
      html += teamRow(team, sel, locked,
        'toggleFollowTeam(\'' + team.replace(/'/g, "\\'") + '\')');
    });
  });
  if (!any) html = '<div class="ob-empty">No teams match "' + filter + '"</div>';
  list.innerHTML = html;
  updateFollowCounter();
}

function filterFollowTeams(val) { renderFollowList(val); }

function toggleFollowTeam(team) {
  var lockedTeams = [selectedMyClub].concat(
    selectedWatchLive.filter(function(t) { return t !== selectedMyClub; })
  );
  if (lockedTeams.indexOf(team) !== -1) {
    showToast('Already in your selection', 'info'); return;
  }
  var idx = selectedFollow.indexOf(team);
  if (idx !== -1) {
    selectedFollow.splice(idx, 1);
  } else {
    if (selectedFollow.length >= 10) { showToast('Maximum 10 teams — remove one first', 'error'); return; }
    selectedFollow.push(team);
  }
  var searchEl = document.getElementById('ob1c-search');
  renderFollowList(searchEl ? searchEl.value : '');
}

function updateFollowCounter() {
  var el = document.getElementById('ob1c-counter');
  if (el) {
    var n = selectedFollow.length;
    el.textContent = n + ' of 10 selected';
    el.className = 'ob-counter' + (n >= 10 ? ' full' : '');
  }
}

function submitFollowTeams() {
  showAuthScreen('auth-onboard2');
  renderBookmakerList();
}

/* ─────────────────────────────────────────
   ALL_BOOKMAKERS (22 operators)
───────────────────────────────────────── */
var ALL_BOOKMAKERS = [
  'Bet365','Sky Bet','Paddy Power','William Hill',
  'Betfair','Coral','Ladbrokes','Betfred',
  '888sport','Unibet','BetVictor','Betway',
  'BoyleSports','Spreadex','QuinnBet','Tote',
  'Mr Green','NetBet','Grosvenor Sport','10bet',
  'Parimatch','Mansion Bet'
];

/* ─────────────────────────────────────────
   ONBOARDING 2 — BOOKMAKERS
───────────────────────────────────────── */
function renderBookmakerList() {
  var list = document.getElementById('ob2-list');
  if (!list) return;
  if (userProfile && userProfile.bookmaker_accounts && !selectedBookmakers.length) {
    selectedBookmakers = (userProfile.bookmaker_accounts || []).slice();
  }
  var html = '';
  ALL_BOOKMAKERS.forEach(function(bookie) {
    var on  = selectedBookmakers.indexOf(bookie) !== -1;
    var tid = 'ob-tog-' + bookie.replace(/\s/g,'_');
    html += '<div class="ob-bookie-row" onclick="toggleBookie(\'' + bookie + '\')">' +
      '<span class="ob-bookie-name">' + bookie + '</span>' +
      '<div class="ob-toggle' + (on ? ' on' : '') + '" id="' + tid + '">' +
        '<div class="ob-toggle-dot"></div>' +
      '</div></div>';
  });
  list.innerHTML = html;
}

function toggleBookie(bookie) {
  var idx = selectedBookmakers.indexOf(bookie);
  if (idx !== -1) { selectedBookmakers.splice(idx, 1); }
  else            { selectedBookmakers.push(bookie); }
  var tog = document.getElementById('ob-tog-' + bookie.replace(/\s/g,'_'));
  if (tog) tog.className = 'ob-toggle' + (selectedBookmakers.indexOf(bookie) !== -1 ? ' on' : '');
}

function submitBookmakers(skip) { saveAllOnboardingData(skip); }

/* ─────────────────────────────────────────
   SAVE — write all four fields at once
───────────────────────────────────────── */
function saveAllOnboardingData(skipBookmakers) {
  var bookiesToSave = skipBookmakers ? [] : selectedBookmakers.slice();

  if (!sbClient || !authUser) {
    hideAuthScreens();
    if (typeof goTo === 'function') goTo(13);
    return;
  }

  sbClient.from('user_profiles').update({
    my_club:            selectedMyClub,
    watch_live_teams:   selectedWatchLive.slice(),
    follow_teams:       selectedFollow.slice(),
    bookmaker_accounts: bookiesToSave,
    updated_at:         new Date().toISOString()
  }).eq('id', authUser.id).then(function(result) {
    if (result.error) {
      console.warn('saveAllOnboardingData error:', result.error.message);
      showToast('Could not save — please try again', 'error');
      return;
    }
    if (userProfile) {
      userProfile.my_club            = selectedMyClub;
      userProfile.watch_live_teams   = selectedWatchLive.slice();
      userProfile.follow_teams       = selectedFollow.slice();
      userProfile.bookmaker_accounts = bookiesToSave;
    }
    showToast('Setup complete!', 'success');
    hideAuthScreens();
    updateProfileScreen();
    if (typeof goTo === 'function') goTo(13);
  });
}

/* ─────────────────────────────────────────
   WINDOW LOAD — runs after existing script
───────────────────────────────────────── */
window.addEventListener('load', function() {
  initAgeGate();
  initSupabase();
});
