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

/* ─────────────────────────────────────────
   MY CLUB — MASTER/DETAIL PANEL DATA
───────────────────────────────────────── */
var selectedLeague1a = 'PREMIER LEAGUE';
var selectedLeague1b = 'PREMIER LEAGUE';
var selectedLeague1c = 'PREMIER LEAGUE';

var LEAGUE_INFO = {
  'PREMIER LEAGUE':        { chip: 'PL',     label: 'Premier League',      color: '#38003C' },
  'CHAMPIONSHIP':          { chip: 'CHAMP',  label: 'Championship',         color: '#EE2E24' },
  'LEAGUE ONE':            { chip: 'L1',     label: 'League One',            color: '#00A650' },
  'LEAGUE TWO':            { chip: 'L2',     label: 'League Two',            color: '#00A0DC' },
  'SCOTTISH PREMIERSHIP':  { chip: 'SPL',    label: 'Scottish Prem.',       color: '#003F7F' },
  'SCOTTISH CHAMPIONSHIP': { chip: 'SCHAMP', label: 'Scot. Champ.',         color: '#003F7F' },
  'SCOTTISH LEAGUE ONE':   { chip: 'SL1',    label: 'Scot. L1',             color: '#003F7F' },
  'SCOTTISH LEAGUE TWO':   { chip: 'SL2',    label: 'Scot. L2',             color: '#003F7F' }
};

/* API-Football team IDs → badge URL: https://media.api-sports.io/football/teams/{id}.png */
var TEAM_IDS = {
  /* Premier League */
  'Arsenal':42,'Aston Villa':66,'Bournemouth':35,'Brentford':55,
  'Brighton':51,'Chelsea':49,'Crystal Palace':52,'Everton':45,
  'Fulham':36,'Ipswich Town':57,'Leicester City':46,'Liverpool':40,
  'Manchester City':50,'Manchester United':33,'Newcastle United':34,
  'Nottingham Forest':65,'Southampton':41,'Tottenham Hotspur':47,
  'West Ham United':48,'Wolverhampton Wanderers':39,
  /* Championship */
  'Burnley':44,'Leeds United':63,'Norwich City':43,'Sheffield United':62,
  'Watford':38,'West Bromwich Albion':67,'Middlesbrough':89,
  'Blackburn Rovers':69,'Hull City':85,'Millwall':90,'Cardiff City':72,
  'Coventry City':75,'Derby County':77,'Stoke City':100,'Swansea City':103,
  'Bristol City':70,'Preston North End':73,'Birmingham City':60,
  'Luton Town':232,'Blackpool':71,'Oxford United':162,'Portsmouth':97,
  'Sheffield Wednesday':68,'Queens Park Rangers':98,'Sunderland':102,
  'Plymouth Argyle':95,
  /* League One */
  'Barnsley':74,'Bolton Wanderers':80,'Charlton Athletic':83,
  'Peterborough United':94,'Reading':99,'Wigan Athletic':104,
  'Rotherham United':96,'Exeter City':84,'Leyton Orient':86,'Lincoln City':91,
  /* League Two */
  'Bradford City':79,'Carlisle United':82,'Colchester United':76,
  'Crewe Alexandra':78,'Swindon Town':105,'Tranmere Rovers':107,'Walsall':109,
  /* Scottish */
  'Celtic':485,'Rangers':489,'Aberdeen':700,
  'Heart of Midlothian':703,'Hibernian':704
};

function getInitials(name) {
  var words = name.replace(/[&']/g,'').split(/\s+/).filter(function(w) {
    return w.length > 1 && !/^(of|the|and|fc|afc)$/i.test(w);
  });
  if (!words.length) return name.substring(0,2).toUpperCase();
  if (words.length === 1) return words[0].substring(0,2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function badgeHtml(team, lgColor) {
  var id  = TEAM_IDS[team];
  var ini = getInitials(team);
  var fb  = '<span class="team-badge-fb" style="background:' + lgColor + '">' + ini + '</span>';
  if (!id) return fb;
  return '<span class="team-badge-wrap">' +
    '<img class="team-badge-img" src="https://media.api-sports.io/football/teams/' + id + '.png" ' +
    'loading="lazy" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' +
    '<span class="team-badge-fb" style="background:' + lgColor + ';display:none">' + ini + '</span>' +
    '</span>';
}

function renderLeaguePanel() {
  var el = document.getElementById('ob1a-leagues');
  if (!el) return;
  var selLg = selectedMyClub ? leagueOf(selectedMyClub) : '';
  var html = '';
  Object.keys(LEAGUE_INFO).forEach(function(lg) {
    var info    = LEAGUE_INFO[lg];
    var isActive = lg === selectedLeague1a;
    var hasPick  = selLg === lg;
    html +=
      '<div class="ob1a-league-item' + (isActive ? ' active' : '') +
      '" onclick="selectLeague1a(\'' + lg.replace(/'/g,"\\'") + '\')">' +
      '<span class="ob1a-league-chip" style="background:' + info.color + '">' + info.chip + '</span>' +
      '<span class="ob1a-league-label">' + info.label + (hasPick ? ' ✓' : '') + '</span>' +
      '</div>';
  });
  el.innerHTML = html;
}

function selectLeague1a(lg) {
  selectedLeague1a = lg;
  var s = document.getElementById('ob1a-search');
  if (s) s.value = '';
  renderLeaguePanel();
  renderMyClubList('');
}

/* ─────────────────────────────────────────
   ONBOARDING 1a — MY CLUB (single, mandatory)
───────────────────────────────────────── */
function teamCard1a(team, lgColor) {
  var sel = selectedMyClub === team;
  return '<div class="ob1a-team-card' + (sel ? ' selected' : '') +
    '" onclick="selectMyClub(\'' + team.replace(/'/g,"\\'") + '\')">' +
    badgeHtml(team, lgColor) +
    '<span class="ob1a-team-name">' + team + '</span>' +
    '<span class="ob1a-tick">' + (sel ? '✓' : '') + '</span>' +
    '</div>';
}

function renderMyClubList(filter) {
  var list = document.getElementById('ob1a-list');
  if (!list) return;
  var q      = (filter || '').toLowerCase().trim();
  var lgInfo = LEAGUE_INFO[selectedLeague1a] || {};
  var lgColor = lgInfo.color || '#666';
  var html = '';

  if (q) {
    /* Search mode — show matching teams across all leagues */
    var any = false;
    Object.keys(ALL_TEAMS).forEach(function(lg) {
      var c = (LEAGUE_INFO[lg] || {}).color || '#666';
      var matches = ALL_TEAMS[lg].filter(function(t) {
        return t.toLowerCase().indexOf(q) !== -1;
      });
      if (!matches.length) return;
      any = true;
      html += '<div class="ob1a-search-lg-hdr">' + lg + '</div>';
      matches.forEach(function(t) { html += teamCard1a(t, c); });
    });
    if (!any) html = '<div class="ob-empty">No teams match "' + q + '"</div>';
  } else {
    /* League mode — show teams for selected league */
    var teams = ALL_TEAMS[selectedLeague1a] || [];
    teams.forEach(function(t) { html += teamCard1a(t, lgColor); });
    if (!teams.length) html = '<div class="ob-empty">No teams</div>';
  }

  list.innerHTML = html;
  updateMyClubCounter();
}

function filterMyClub(val) { renderMyClubList(val); }

function selectMyClub(team) {
  selectedMyClub = team;
  var lg = leagueOf(team);
  if (lg) selectedLeague1a = lg;
  var searchEl = document.getElementById('ob1a-search');
  renderLeaguePanel();
  renderMyClubList(searchEl ? searchEl.value : '');
}

/* ─────────────────────────────────────────
   ONBOARDING 1b — WATCH LIVE PANEL HELPERS
───────────────────────────────────────── */
function teamCard1bc(team, lgColor, isSelected, isLocked, onclick) {
  var sel  = isSelected || isLocked;
  var tick = isLocked
    ? '<span class="ob1a-tick" style="font-size:10px;border-color:var(--ink4);color:var(--ink4);background:transparent">🔒</span>'
    : '<span class="ob1a-tick">' + (isSelected ? '✓' : '') + '</span>';
  return '<div class="ob1a-team-card' + (sel ? ' selected' : '') + '"' +
    (isLocked ? '' : ' onclick="' + onclick + '"') + '>' +
    badgeHtml(team, lgColor) +
    '<span class="ob1a-team-name">' + team + '</span>' +
    tick +
    '</div>';
}

function renderLeaguePanel1b() {
  var el = document.getElementById('ob1b-leagues');
  if (!el) return;
  var html = '';
  Object.keys(LEAGUE_INFO).forEach(function(lg) {
    var info     = LEAGUE_INFO[lg];
    var isActive = lg === selectedLeague1b;
    html +=
      '<div class="ob1a-league-item' + (isActive ? ' active' : '') +
      '" onclick="selectLeague1b(\'' + lg.replace(/'/g,"\\'") + '\')">' +
      '<span class="ob1a-league-chip" style="background:' + info.color + '">' + info.chip + '</span>' +
      '<span class="ob1a-league-label">' + info.label + '</span>' +
      '</div>';
  });
  el.innerHTML = html;
}

function selectLeague1b(lg) {
  selectedLeague1b = lg;
  var s = document.getElementById('ob1b-search');
  if (s) s.value = '';
  renderLeaguePanel1b();
  renderWatchLiveList('');
}

/* ─────────────────────────────────────────
   ONBOARDING 1c — FOLLOW TEAMS PANEL HELPERS
───────────────────────────────────────── */
function renderLeaguePanel1c() {
  var el = document.getElementById('ob1c-leagues');
  if (!el) return;
  var html = '';
  Object.keys(LEAGUE_INFO).forEach(function(lg) {
    var info     = LEAGUE_INFO[lg];
    var isActive = lg === selectedLeague1c;
    html +=
      '<div class="ob1a-league-item' + (isActive ? ' active' : '') +
      '" onclick="selectLeague1c(\'' + lg.replace(/'/g,"\\'") + '\')">' +
      '<span class="ob1a-league-chip" style="background:' + info.color + '">' + info.chip + '</span>' +
      '<span class="ob1a-league-label">' + info.label + '</span>' +
      '</div>';
  });
  el.innerHTML = html;
}

function selectLeague1c(lg) {
  selectedLeague1c = lg;
  var s = document.getElementById('ob1c-search');
  if (s) s.value = '';
  renderLeaguePanel1c();
  renderFollowList('');
}

/* Helper: safe HTML render of a team row (used by 1b + 1c screens) */
function teamRow(team, isSelected, isLocked, onclick) {
  var sel  = isSelected || isLocked;
  var icon = isLocked ? '🔒' : (isSelected ? '✓' : '');
  return '<div class="ob-team-row' + (sel ? ' selected' : '') + '"' +
    (isLocked ? '' : ' onclick="' + onclick + '"') + '>' +
    '<span class="ob-team-name">' + team + '</span>' +
    '<span class="ob-check">' + icon + '</span>' +
    '</div>';
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
}

/* ─────────────────────────────────────────
   ONBOARDING 1b — WATCH LIVE (up to 5, My Club locked)
───────────────────────────────────────── */
function answerGoesToMatches(yes) {
  goesToMatches = yes;
  var activeSt = 'flex:1;padding:10px;border-radius:9px;font-family:var(--fs);font-size:13px;font-weight:700;border:1.5px solid white;background:white;color:var(--ink);cursor:pointer;';
  var idleSt   = 'flex:1;padding:10px;border-radius:9px;font-family:var(--fs);font-size:13px;font-weight:700;border:1.5px solid rgba(255,255,255,0.28);background:transparent;color:rgba(255,255,255,0.75);cursor:pointer;';
  var yBtn = document.getElementById('ob1b-yes');
  var nBtn = document.getElementById('ob1b-no');
  if (yBtn) yBtn.setAttribute('style', yes ? activeSt : idleSt);
  if (nBtn) nBtn.setAttribute('style', !yes ? activeSt : idleSt);

  if (!yes) {
    selectedWatchLive = [selectedMyClub];
    showAuthScreen('auth-onboard1c');
    return;
  }

  // Set default league to My Club's league
  var myLeague = leagueOf(selectedMyClub);
  if (myLeague) selectedLeague1b = myLeague;

  var bodyEl    = document.getElementById('ob1b-body');
  var footerEl  = document.getElementById('ob1b-footer');
  var counterEl = document.getElementById('ob1b-counter');
  if (bodyEl)    bodyEl.style.display    = 'flex';
  if (footerEl)  footerEl.style.display  = '';
  if (counterEl) counterEl.style.display = '';

  renderLeaguePanel1b();
  renderWatchLiveList('');
}

function renderWatchLiveList(filter) {
  var list = document.getElementById('ob1b-list');
  if (!list) return;
  var q    = (filter || '').toLowerCase().trim();
  var html = '';

  if (q) {
    var any = false;
    Object.keys(ALL_TEAMS).forEach(function(lg) {
      var c     = (LEAGUE_INFO[lg] || {}).color || '#666';
      var teams = ALL_TEAMS[lg].filter(function(t) {
        return t.toLowerCase().indexOf(q) !== -1;
      });
      if (!teams.length) return;
      any = true;
      html += '<div class="ob1a-search-lg-hdr">' + lg + '</div>';
      teams.forEach(function(team) {
        var locked = team === selectedMyClub;
        var sel    = selectedWatchLive.indexOf(team) !== -1;
        html += teamCard1bc(team, c, sel, locked,
          'toggleWatchLiveTeam(\'' + team.replace(/'/g, "\\'") + '\')');
      });
    });
    if (!any) html = '<div class="ob-empty">No teams match "' + q + '"</div>';
  } else {
    var lgInfo  = LEAGUE_INFO[selectedLeague1b] || {};
    var lgColor = lgInfo.color || '#666';
    var teams   = ALL_TEAMS[selectedLeague1b] || [];
    if (teams.length) {
      teams.forEach(function(team) {
        var locked = team === selectedMyClub;
        var sel    = selectedWatchLive.indexOf(team) !== -1;
        html += teamCard1bc(team, lgColor, sel, locked,
          'toggleWatchLiveTeam(\'' + team.replace(/'/g, "\\'") + '\')');
      });
    } else {
      html = '<div class="ob-empty">No teams</div>';
    }
  }

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
}

/* ─────────────────────────────────────────
   ONBOARDING 1c — FOLLOW TEAMS (up to 10)
───────────────────────────────────────── */
function renderFollowList(filter) {
  var list = document.getElementById('ob1c-list');
  if (!list) return;
  var q           = (filter || '').toLowerCase().trim();
  var myLeague    = leagueOf(selectedMyClub);
  var lockedTeams = [selectedMyClub].concat(
    selectedWatchLive.filter(function(t) { return t !== selectedMyClub; })
  );
  var html = '';

  if (q) {
    var any = false;
    Object.keys(ALL_TEAMS).forEach(function(lg) {
      var c     = (LEAGUE_INFO[lg] || {}).color || '#666';
      var teams = ALL_TEAMS[lg].filter(function(t) {
        return t.toLowerCase().indexOf(q) !== -1;
      });
      if (!teams.length) return;
      any = true;
      html += '<div class="ob1a-search-lg-hdr">' + lg + (lg === myLeague ? ' ★' : '') + '</div>';
      teams.forEach(function(team) {
        var locked = lockedTeams.indexOf(team) !== -1;
        var sel    = selectedFollow.indexOf(team) !== -1;
        html += teamCard1bc(team, c, sel, locked,
          'toggleFollowTeam(\'' + team.replace(/'/g, "\\'") + '\')');
      });
    });
    if (!any) html = '<div class="ob-empty">No teams match "' + q + '"</div>';
  } else {
    var lgInfo  = LEAGUE_INFO[selectedLeague1c] || {};
    var lgColor = lgInfo.color || '#666';
    var teams   = ALL_TEAMS[selectedLeague1c] || [];
    if (teams.length) {
      teams.forEach(function(team) {
        var locked = lockedTeams.indexOf(team) !== -1;
        var sel    = selectedFollow.indexOf(team) !== -1;
        html += teamCard1bc(team, lgColor, sel, locked,
          'toggleFollowTeam(\'' + team.replace(/'/g, "\\'") + '\')');
      });
    } else {
      html = '<div class="ob-empty">No teams</div>';
    }
  }

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
