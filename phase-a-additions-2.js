/* ═══════════════════════════════════════════════════════════
   PHASE A — PART 2 (revised): Three-tier team onboarding
   + Bookmakers + window load handler
   ═══════════════════════════════════════════════════════════ */

/* ── Onboarding state ── */
var selectedMyClub    = '';   // single string — auth-onboard1a
var selectedWatchLive = [];   // up to 5 — auth-onboard1b Watch Live tab
var selectedFollow    = [];   // up to 10 — auth-onboard1b Follow Scores tab
var selectedBookmakers = [];  // auth-onboard2
var ob1bActiveTab     = 'watchlive'; // 'watchlive' | 'followscores'

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
var selectedLeague1b = 'PREMIER LEAGUE'; // shared across both tabs on 1b

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
function teamCard1bc(team, lgColor, isSelected, isLocked, onclick, sublabel) {
  var sel  = isSelected || isLocked;
  var tick = isLocked
    ? '<span class="ob1a-tick" style="font-size:10px;border-color:var(--ink4);color:var(--ink4);background:transparent">🔒</span>'
    : '<span class="ob1a-tick">' + (isSelected ? '✓' : '') + '</span>';
  var sub = sublabel
    ? '<span style="font-family:var(--fm);font-size:8px;color:var(--ink5);display:block;margin-top:1px">' + sublabel + '</span>'
    : '';
  return '<div class="ob1a-team-card' + (sel ? ' selected' : '') + '"' +
    (isLocked ? '' : ' onclick="' + onclick + '"') + '>' +
    badgeHtml(team, lgColor) +
    '<span class="ob1a-team-name">' + team + sub + '</span>' +
    tick +
    '</div>';
}

/* ─────────────────────────────────────────
   ONBOARDING 1b — COMBINED: WATCH LIVE + FOLLOW SCORES
───────────────────────────────────────── */
var OB1B_SUBTITLES = {
  watchlive:    'Teams you attend in person — up to 5. We\'ll show pubs, transport and tickets for their matchdays.',
  followscores: 'Teams whose scores you want to track — up to 10. Shown on your home screen.'
};

function ob1bInitScreen() {
  ob1bActiveTab = 'watchlive';
  var myLeague = leagueOf(selectedMyClub);
  if (myLeague) selectedLeague1b = myLeague;
  var s = document.getElementById('ob1b-search');
  if (s) s.value = '';
  ob1bUpdateTabStyles();
  ob1bRenderLeaguePanel();
  ob1bRenderTeamList('');
  ob1bUpdateUI();
}

function ob1bSwitchTab(tab) {
  ob1bActiveTab = tab;
  var s = document.getElementById('ob1b-search');
  if (s) s.value = '';
  ob1bUpdateTabStyles();
  ob1bRenderLeaguePanel();
  ob1bRenderTeamList('');
  ob1bUpdateUI();
}

function ob1bUpdateTabStyles() {
  var wlBtn = document.getElementById('ob1b-tab-wl');
  var fsBtn = document.getElementById('ob1b-tab-fs');
  var activeSt = 'flex:1;padding:7px 8px;border-radius:20px;font-family:var(--fs);font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid rgba(255,255,255,0.5);background:rgba(255,255,255,0.18);color:#fff;transition:all 0.15s;';
  var idleSt   = 'flex:1;padding:7px 8px;border-radius:20px;font-family:var(--fs);font-size:11px;font-weight:700;cursor:pointer;border:1.5px solid rgba(255,255,255,0.2);background:transparent;color:rgba(255,255,255,0.5);transition:all 0.15s;';
  if (wlBtn) wlBtn.setAttribute('style', ob1bActiveTab === 'watchlive'    ? activeSt : idleSt);
  if (fsBtn) fsBtn.setAttribute('style', ob1bActiveTab === 'followscores' ? activeSt : idleSt);
}

function ob1bUpdateUI() {
  var wlCount = document.getElementById('ob1b-wl-count');
  var fsCount = document.getElementById('ob1b-fs-count');
  if (wlCount) wlCount.textContent = selectedWatchLive.length;
  if (fsCount) fsCount.textContent = selectedFollow.length;

  var sub = document.getElementById('ob1b-tab-sub');
  if (sub) sub.textContent = OB1B_SUBTITLES[ob1bActiveTab] || '';

  var ctr = document.getElementById('ob1b-counter');
  if (ctr) {
    if (ob1bActiveTab === 'watchlive') {
      var n = selectedWatchLive.length;
      ctr.textContent = n + ' of 5 selected';
      ctr.className = 'ob-counter' + (n >= 5 ? ' full' : '');
    } else {
      var m = selectedFollow.length;
      ctr.textContent = m + ' of 10 selected';
      ctr.className = 'ob-counter' + (m >= 10 ? ' full' : '');
    }
  }
}

function ob1bRenderLeaguePanel() {
  var el = document.getElementById('ob1b-leagues');
  if (!el) return;
  var html = '';
  Object.keys(LEAGUE_INFO).forEach(function(lg) {
    var info     = LEAGUE_INFO[lg];
    var isActive = lg === selectedLeague1b;
    html +=
      '<div class="ob1a-league-item' + (isActive ? ' active' : '') +
      '" onclick="ob1bSelectLeague(\'' + lg.replace(/'/g, "\\'") + '\')">' +
      '<span class="ob1a-league-chip" style="background:' + info.color + '">' + info.chip + '</span>' +
      '<span class="ob1a-league-label">' + info.label + '</span>' +
      '</div>';
  });
  el.innerHTML = html;
}

function ob1bSelectLeague(lg) {
  selectedLeague1b = lg;
  var s = document.getElementById('ob1b-search');
  if (s) s.value = '';
  ob1bRenderLeaguePanel();
  ob1bRenderTeamList('');
}

function ob1bFilterTeams(val) { ob1bRenderTeamList(val); }

function ob1bRenderTeamList(filter) {
  var list = document.getElementById('ob1b-list');
  if (!list) return;
  var q    = (filter || '').toLowerCase().trim();
  var html = '';

  if (ob1bActiveTab === 'watchlive') {
    if (q) {
      var any = false;
      Object.keys(ALL_TEAMS).forEach(function(lg) {
        var c     = (LEAGUE_INFO[lg] || {}).color || '#666';
        var teams = ALL_TEAMS[lg].filter(function(t) { return t.toLowerCase().indexOf(q) !== -1; });
        if (!teams.length) return;
        any = true;
        html += '<div class="ob1a-search-lg-hdr">' + lg + '</div>';
        teams.forEach(function(team) {
          var locked = team === selectedMyClub;
          var sel    = selectedWatchLive.indexOf(team) !== -1;
          html += teamCard1bc(team, c, sel, locked,
            'ob1bToggleTeam(\'' + team.replace(/'/g, "\\'") + '\')', '');
        });
      });
      if (!any) html = '<div class="ob-empty">No teams match "' + q + '"</div>';
    } else {
      var lgC  = (LEAGUE_INFO[selectedLeague1b] || {}).color || '#666';
      var wlTeams = ALL_TEAMS[selectedLeague1b] || [];
      wlTeams.forEach(function(team) {
        var locked = team === selectedMyClub;
        var sel    = selectedWatchLive.indexOf(team) !== -1;
        html += teamCard1bc(team, lgC, sel, locked,
          'ob1bToggleTeam(\'' + team.replace(/'/g, "\\'") + '\')', '');
      });
      if (!wlTeams.length) html = '<div class="ob-empty">No teams</div>';
    }
  } else {
    /* Follow Scores tab — WL teams appear locked with "from Watch Live" label */
    if (q) {
      var any2 = false;
      Object.keys(ALL_TEAMS).forEach(function(lg) {
        var c2    = (LEAGUE_INFO[lg] || {}).color || '#666';
        var teams2 = ALL_TEAMS[lg].filter(function(t) { return t.toLowerCase().indexOf(q) !== -1; });
        if (!teams2.length) return;
        any2 = true;
        html += '<div class="ob1a-search-lg-hdr">' + lg + '</div>';
        teams2.forEach(function(team) {
          var isWL   = selectedWatchLive.indexOf(team) !== -1;
          var sel    = selectedFollow.indexOf(team) !== -1 || isWL;
          html += teamCard1bc(team, c2, sel, isWL,
            'ob1bToggleTeam(\'' + team.replace(/'/g, "\\'") + '\')',
            isWL ? 'from Watch Live' : '');
        });
      });
      if (!any2) html = '<div class="ob-empty">No teams match "' + q + '"</div>';
    } else {
      var lgC2   = (LEAGUE_INFO[selectedLeague1b] || {}).color || '#666';
      var fsTeams = ALL_TEAMS[selectedLeague1b] || [];
      fsTeams.forEach(function(team) {
        var isWL   = selectedWatchLive.indexOf(team) !== -1;
        var sel    = selectedFollow.indexOf(team) !== -1 || isWL;
        html += teamCard1bc(team, lgC2, sel, isWL,
          'ob1bToggleTeam(\'' + team.replace(/'/g, "\\'") + '\')',
          isWL ? 'from Watch Live' : '');
      });
      if (!fsTeams.length) html = '<div class="ob-empty">No teams</div>';
    }
  }

  list.innerHTML = html;
  ob1bUpdateUI();
}

function ob1bToggleTeam(team) {
  if (ob1bActiveTab === 'watchlive') {
    if (team === selectedMyClub) { showToast('Your club is always included', 'info'); return; }
    var idx = selectedWatchLive.indexOf(team);
    if (idx !== -1) {
      selectedWatchLive.splice(idx, 1);
    } else {
      if (selectedWatchLive.length >= 5) { showToast('Maximum 5 teams for Watch Live — remove one first', 'error'); return; }
      selectedWatchLive.push(team);
      if (selectedFollow.indexOf(team) === -1 && selectedFollow.length < 10) {
        selectedFollow.push(team);
      }
    }
  } else {
    if (selectedWatchLive.indexOf(team) !== -1) { showToast('Already added via Watch Live', 'info'); return; }
    var idx2 = selectedFollow.indexOf(team);
    if (idx2 !== -1) {
      selectedFollow.splice(idx2, 1);
    } else {
      if (selectedFollow.length >= 10) { showToast('Maximum 10 teams — remove one first', 'error'); return; }
      selectedFollow.push(team);
    }
  }
  var searchEl = document.getElementById('ob1b-search');
  ob1bRenderTeamList(searchEl ? searchEl.value : '');
}

function submitAddTeams() {
  /* Ensure all WL teams are in the follow list before saving */
  selectedWatchLive.forEach(function(t) {
    if (selectedFollow.indexOf(t) === -1) selectedFollow.push(t);
  });
  showAuthScreen('auth-onboard2');
  renderBookmakerList();
}

/* ─────────────────────────────────────────
   SKIP CONFIRMATION DIALOG
───────────────────────────────────────── */
function ob1bShowSkipDialog() {
  var dlg = document.getElementById('ob1b-skip-dialog');
  if (dlg) dlg.style.display = 'flex';
}

function ob1bSkipCancel() {
  var dlg = document.getElementById('ob1b-skip-dialog');
  if (dlg) dlg.style.display = 'none';
}

function ob1bSkipConfirm() {
  var dlg = document.getElementById('ob1b-skip-dialog');
  if (dlg) dlg.style.display = 'none';
  selectedWatchLive = selectedMyClub ? [selectedMyClub] : [];
  selectedFollow    = selectedMyClub ? [selectedMyClub] : [];
  showAuthScreen('auth-onboard2');
  renderBookmakerList();
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
