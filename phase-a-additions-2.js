/* ═══════════════════════════════════════════════════════════
   PHASE A — PART 2: Teams · Bookmakers · Onboarding · Init
   ═══════════════════════════════════════════════════════════ */

/* ─────────────────────────────────────────
   ONBOARDING STATE
───────────────────────────────────────── */
var selectedTeams     = [];
var selectedBookmakers = [];

/* ─────────────────────────────────────────
   ALL_TEAMS
   NOTE: These lists reflect the 2024/25 season.
   Review every summer — promotion/relegation
   changes membership annually.
   Long-term: replace with live call to the
   API-Football /teams endpoint.
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

/* ─────────────────────────────────────────
   TEAM ONBOARDING — render / toggle / save
───────────────────────────────────────── */
function renderTeamsList(filter) {
  var list = document.getElementById('ob1-list');
  if (!list) return;

  var q = (filter || '').toLowerCase().trim();
  var html = '';
  var anyResult = false;

  Object.keys(ALL_TEAMS).forEach(function(league) {
    var teams = ALL_TEAMS[league].filter(function(t) {
      return !q || t.toLowerCase().indexOf(q) !== -1;
    });
    if (!teams.length) return;
    anyResult = true;

    html += '<div class="ob-league-hdr">'+league+'</div>';
    teams.forEach(function(team) {
      var sel = selectedTeams.indexOf(team) !== -1;
      html +=
        '<div class="ob-team-row'+(sel?' selected':'')+'" onclick="toggleTeam(\''+team.replace(/'/g,"\\'")+'\')">' +
          '<span class="ob-team-name">'+team+'</span>' +
          '<span class="ob-check">'+(sel ? '✓' : '')+'</span>' +
        '</div>';
    });
  });

  if (!anyResult) {
    html = '<div class="ob-empty">No teams match "'+filter+'"</div>';
  }

  list.innerHTML = html;
  updateTeamCounter();
}

function filterTeams(val) {
  renderTeamsList(val);
}

function toggleTeam(team) {
  var idx = selectedTeams.indexOf(team);
  if (idx !== -1) {
    selectedTeams.splice(idx, 1);
  } else {
    if (selectedTeams.length >= 5) {
      showToast('Maximum 5 teams — remove one first', 'error');
      return;
    }
    selectedTeams.push(team);
  }
  // Re-render with current search value
  var searchEl = document.getElementById('ob1-search');
  renderTeamsList(searchEl ? searchEl.value : '');
}

function updateTeamCounter() {
  var counter = document.getElementById('ob1-counter');
  if (!counter) return;
  var n = selectedTeams.length;
  counter.textContent = n + ' of 5 selected';
  counter.className = 'ob-counter' + (n === 5 ? ' full' : '');
}

function submitTeams() { saveTeams(); }

function saveTeams() {
  if (!sbClient || !authUser) {
    // Offline / demo — just advance
    showAuthScreen('auth-onboard2');
    renderBookmakerList();
    return;
  }
  sbClient
    .from('user_profiles')
    .update({ favourite_teams: selectedTeams, updated_at: new Date().toISOString() })
    .eq('id', authUser.id)
    .then(function(result) {
      if (result.error) { showToast('Could not save teams — try again', 'error'); return; }
      if (userProfile) userProfile.favourite_teams = selectedTeams.slice();
      showAuthScreen('auth-onboard2');
      renderBookmakerList();
    });
}

/* ─────────────────────────────────────────
   ALL_BOOKMAKERS
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
   BOOKMAKER ONBOARDING — render / toggle / save
───────────────────────────────────────── */
function renderBookmakerList() {
  var list = document.getElementById('ob2-list');
  if (!list) return;

  // Pre-populate from saved profile if available
  if (userProfile && userProfile.bookmaker_accounts && !selectedBookmakers.length) {
    selectedBookmakers = (userProfile.bookmaker_accounts || []).slice();
  }

  var html = '';
  ALL_BOOKMAKERS.forEach(function(bookie) {
    var on = selectedBookmakers.indexOf(bookie) !== -1;
    html +=
      '<div class="ob-bookie-row" onclick="toggleBookie(\''+bookie+'\')">'+
        '<span class="ob-bookie-name">'+bookie+'</span>'+
        '<div class="ob-toggle'+(on?' on':'')+'" id="ob-tog-'+bookie.replace(/\s/g,'_')+'">'+
          '<div class="ob-toggle-dot"></div>'+
        '</div>'+
      '</div>';
  });

  list.innerHTML = html;
}

function toggleBookie(bookie) {
  var idx = selectedBookmakers.indexOf(bookie);
  if (idx !== -1) {
    selectedBookmakers.splice(idx, 1);
  } else {
    selectedBookmakers.push(bookie);
  }
  // Update just the toggle UI — no full re-render needed
  var togId = 'ob-tog-' + bookie.replace(/\s/g,'_');
  var tog = document.getElementById(togId);
  if (tog) {
    var on = selectedBookmakers.indexOf(bookie) !== -1;
    tog.className = 'ob-toggle' + (on ? ' on' : '');
  }
}

function submitBookmakers(skip) { saveBookmakers(skip); }

function saveBookmakers(skip) {
  var toSave = skip ? [] : selectedBookmakers.slice();

  if (!sbClient || !authUser) {
    // Offline / demo — go straight to profile
    hideAuthScreens();
    if (typeof goTo === 'function') goTo(13);
    return;
  }

  sbClient
    .from('user_profiles')
    .update({ bookmaker_accounts: toSave, updated_at: new Date().toISOString() })
    .eq('id', authUser.id)
    .then(function(result) {
      if (result.error) { showToast('Could not save — try again', 'error'); return; }
      if (userProfile) userProfile.bookmaker_accounts = toSave;
      showToast('Setup complete!', 'success');
      hideAuthScreens();
      updateProfileScreen();
      if (typeof goTo === 'function') goTo(13);
    });
}

/* ─────────────────────────────────────────
   WINDOW LOAD HANDLER
   Must run after the existing script block
   has defined goTo() and built the DOM.
───────────────────────────────────────── */
window.addEventListener('load', function() {
  initAgeGate();
  initSupabase();
});
