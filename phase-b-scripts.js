/* ═══════════════════════════════════════════════════════════
   PHASE B — Odds + Offers
   Injected after phase-a-additions-2.js by build.py
   ═══════════════════════════════════════════════════════════ */

/* ─────────────────────────────────────────
   AFFILIATE URLS
   TODO Gate 2: replace all values with real tracked affiliate URLs before going live
───────────────────────────────────────── */
var AFFILIATE_URLS = {
  'Bet365':          'https://www.bet365.com/',
  'Sky Bet':         'https://www.skybet.com/',
  'Paddy Power':     'https://www.paddypower.com/',
  'William Hill':    'https://www.williamhill.com/',
  'Betfair':         'https://www.betfair.com/',
  'Coral':           'https://www.coral.co.uk/',
  'Ladbrokes':       'https://www.ladbrokes.com/',
  'Betfred':         'https://www.betfred.com/',
  '888sport':        'https://www.888sport.com/',
  'Unibet':          'https://www.unibet.co.uk/',
  'BetVictor':       'https://www.betvictor.com/',
  'Betway':          'https://www.betway.com/',
  'BoyleSports':     'https://www.boylesports.com/',
  'Spreadex':        'https://www.spreadex.com/',
  'QuinnBet':        'https://www.quinnbet.com/',
  'Tote':            'https://www.tote.co.uk/',
  'Mr Green':        'https://www.mrgreen.com/',
  'NetBet':          'https://www.netbet.co.uk/',
  'Grosvenor Sport': 'https://www.grosvenorsport.com/',
  '10bet':           'https://www.10bet.co.uk/',
  'Parimatch':       'https://www.parimatch.co.uk/',
  'Mansion Bet':     'https://www.mansionbet.com/'
};

/* UKGC licence numbers — displayed in odds comparison rows */
var BOOKIE_LICENCES = {
  'Bet365':          '39563',
  'Sky Bet':         '38718',
  'Paddy Power':     '44540',
  'William Hill':    '39225',
  'Betfair':         '39470',
  'Coral':           '44548',
  'Ladbrokes':       '44548',
  'Betfred':         '42484',
  '888sport':        '39469',
  'Unibet':          '39218',
  'BetVictor':       '39198',
  'Betway':          '39372',
  'BoyleSports':     '44604',
  'Spreadex':        '44408',
  'QuinnBet':        '54989',
  'Tote':            '44416',
  'Mr Green':        '54973',
  'NetBet':          '39372',
  'Grosvenor Sport': '39378',
  '10bet':           '39451',
  'Parimatch':       '57149',
  'Mansion Bet':     '40769'
};

/* ─────────────────────────────────────────
   MOCK ODDS
   TODO Phase B live: replace MOCK_ODDS with Supabase query when The Odds API is connected
───────────────────────────────────────── */
var MOCK_ODDS = [
  {
    matchId:       'match_ars_che',
    homeTeam:      'Arsenal',
    awayTeam:      'Chelsea',
    competition:   'Premier League',
    commenceTime:  '2026-04-19T15:00:00Z',
    markets: {
      h2h: [
        { bookmaker: 'Bet365',       home: 2.10, draw: 3.40, away: 3.60 },
        { bookmaker: 'Sky Bet',      home: 2.05, draw: 3.50, away: 3.70 },
        { bookmaker: 'Paddy Power',  home: 2.15, draw: 3.30, away: 3.55 },
        { bookmaker: 'William Hill', home: 2.00, draw: 3.40, away: 3.80 },
        { bookmaker: 'Betfair',      home: 2.12, draw: 3.45, away: 3.65 },
        { bookmaker: 'Coral',        home: 2.05, draw: 3.40, away: 3.60 }
      ],
      btts: [
        { bookmaker: 'Bet365',       yes: 1.80, no: 2.00 },
        { bookmaker: 'Sky Bet',      yes: 1.83, no: 1.95 },
        { bookmaker: 'Paddy Power',  yes: 1.85, no: 1.95 },
        { bookmaker: 'William Hill', yes: 1.80, no: 2.00 },
        { bookmaker: 'Betfair',      yes: 1.88, no: 1.96 },
        { bookmaker: 'Coral',        yes: 1.80, no: 1.95 }
      ],
      over_25: [
        { bookmaker: 'Bet365',       over: 1.85, under: 1.95 },
        { bookmaker: 'Sky Bet',      over: 1.90, under: 1.90 },
        { bookmaker: 'Paddy Power',  over: 1.87, under: 1.93 },
        { bookmaker: 'William Hill', over: 1.83, under: 1.97 },
        { bookmaker: 'Betfair',      over: 1.92, under: 1.91 },
        { bookmaker: 'Coral',        over: 1.85, under: 1.95 }
      ]
    }
  },
  {
    matchId:       'match_mci_liv',
    homeTeam:      'Manchester City',
    awayTeam:      'Liverpool',
    competition:   'Premier League',
    commenceTime:  '2026-04-20T16:30:00Z',
    markets: {
      h2h: [
        { bookmaker: 'Bet365',       home: 2.25, draw: 3.30, away: 3.10 },
        { bookmaker: 'Sky Bet',      home: 2.20, draw: 3.40, away: 3.15 },
        { bookmaker: 'Paddy Power',  home: 2.30, draw: 3.25, away: 3.05 },
        { bookmaker: 'William Hill', home: 2.20, draw: 3.30, away: 3.20 },
        { bookmaker: 'Betfair',      home: 2.28, draw: 3.35, away: 3.12 },
        { bookmaker: 'Ladbrokes',    home: 2.22, draw: 3.30, away: 3.10 }
      ],
      btts: [
        { bookmaker: 'Bet365',       yes: 1.72, no: 2.10 },
        { bookmaker: 'Sky Bet',      yes: 1.75, no: 2.05 },
        { bookmaker: 'Paddy Power',  yes: 1.73, no: 2.08 },
        { bookmaker: 'William Hill', yes: 1.70, no: 2.10 },
        { bookmaker: 'Betfair',      yes: 1.76, no: 2.06 },
        { bookmaker: 'Ladbrokes',    yes: 1.72, no: 2.08 }
      ],
      over_25: [
        { bookmaker: 'Bet365',       over: 1.80, under: 2.00 },
        { bookmaker: 'Sky Bet',      over: 1.83, under: 1.97 },
        { bookmaker: 'Paddy Power',  over: 1.82, under: 1.98 },
        { bookmaker: 'William Hill', over: 1.78, under: 2.02 },
        { bookmaker: 'Betfair',      over: 1.85, under: 1.97 },
        { bookmaker: 'Ladbrokes',    over: 1.80, under: 2.00 }
      ]
    }
  },
  {
    matchId:       'match_cel_ran',
    homeTeam:      'Celtic',
    awayTeam:      'Rangers',
    competition:   'Scottish Premiership',
    commenceTime:  '2026-04-21T12:30:00Z',
    markets: {
      h2h: [
        { bookmaker: 'Bet365',       home: 1.95, draw: 3.50, away: 4.00 },
        { bookmaker: 'Sky Bet',      home: 1.90, draw: 3.60, away: 4.20 },
        { bookmaker: 'Paddy Power',  home: 2.00, draw: 3.40, away: 3.90 },
        { bookmaker: 'William Hill', home: 1.91, draw: 3.55, away: 4.10 },
        { bookmaker: 'BoyleSports',  home: 2.05, draw: 3.40, away: 3.80 },
        { bookmaker: 'Coral',        home: 1.95, draw: 3.50, away: 4.00 }
      ],
      btts: [
        { bookmaker: 'Bet365',       yes: 1.90, no: 1.90 },
        { bookmaker: 'Sky Bet',      yes: 1.91, no: 1.90 },
        { bookmaker: 'Paddy Power',  yes: 1.93, no: 1.87 },
        { bookmaker: 'William Hill', yes: 1.88, no: 1.92 },
        { bookmaker: 'BoyleSports',  yes: 1.95, no: 1.85 },
        { bookmaker: 'Coral',        yes: 1.90, no: 1.90 }
      ],
      over_25: [
        { bookmaker: 'Bet365',       over: 1.90, under: 1.90 },
        { bookmaker: 'Sky Bet',      over: 1.88, under: 1.92 },
        { bookmaker: 'Paddy Power',  over: 1.92, under: 1.88 },
        { bookmaker: 'William Hill', over: 1.87, under: 1.93 },
        { bookmaker: 'BoyleSports',  over: 1.95, under: 1.85 },
        { bookmaker: 'Coral',        over: 1.90, under: 1.90 }
      ]
    }
  }
];

/* ─────────────────────────────────────────
   OFFERS FALLBACK DATA
   Shown when Supabase is not connected or returns empty
───────────────────────────────────────── */
var OFFERS_FALLBACK = [
  {
    id: 1, operator_name: 'Bet365', offer_type: 'free_bet',
    title: 'Bet £10, Get £30 in Free Bets',
    subtitle: 'New UK customers. Min odds 1/5.',
    is_featured: true, is_active: true, is_spreadex: false,
    min_deposit_gbp: 10, wagering_req: 1, min_odds: '1/5', expiry_days: 30,
    tc_summary: 'New customers only. 18+. T&Cs apply.',
    ukgc_licence_no: '39563', affiliate_url: 'https://www.bet365.com/',
    accent_hex: '0070CC', display_order: 1
  },
  {
    id: 2, operator_name: 'Sky Bet', offer_type: 'welcome_bonus',
    title: 'Bet £5, Get £20 in Free Bets',
    subtitle: 'New customers only. Min deposit £5.',
    is_featured: false, is_active: true, is_spreadex: false,
    min_deposit_gbp: 5, wagering_req: 1, min_odds: '1/2', expiry_days: 7,
    tc_summary: 'New customers only. 18+. T&Cs apply.',
    ukgc_licence_no: '38718', affiliate_url: 'https://www.skybet.com/',
    accent_hex: '0C2340', display_order: 2
  },
  {
    id: 3, operator_name: 'Paddy Power', offer_type: 'cashback',
    title: 'Money Back as Cash Up To £20',
    subtitle: 'If your first bet loses.',
    is_featured: false, is_active: true, is_spreadex: false,
    min_deposit_gbp: 5, wagering_req: 0, min_odds: '1/5', expiry_days: null,
    tc_summary: 'New UK customers. Max refund £20. 18+.',
    ukgc_licence_no: '44540', affiliate_url: 'https://www.paddypower.com/',
    accent_hex: '007A3D', display_order: 3
  },
  {
    id: 4, operator_name: 'William Hill', offer_type: 'free_bet',
    title: 'Bet £10, Get £30 in Free Bets',
    subtitle: 'New UK customers online only.',
    is_featured: false, is_active: true, is_spreadex: false,
    min_deposit_gbp: 10, wagering_req: 1, min_odds: '1/2', expiry_days: 28,
    tc_summary: 'New customers only. 18+. T&Cs apply.',
    ukgc_licence_no: '39225', affiliate_url: 'https://www.williamhill.com/',
    accent_hex: '83002A', display_order: 4
  },
  {
    id: 5, operator_name: 'Betfair', offer_type: 'welcome_bonus',
    title: 'Bet £10, Get £30 in Free Bets',
    subtitle: 'New customers. Exchange or Sportsbook.',
    is_featured: false, is_active: true, is_spreadex: false,
    min_deposit_gbp: 10, wagering_req: 1, min_odds: '1/5', expiry_days: 30,
    tc_summary: '18+. T&Cs apply. New customers only.',
    ukgc_licence_no: '39470', affiliate_url: 'https://www.betfair.com/',
    accent_hex: 'F5A623', display_order: 5
  },
  {
    id: 6, operator_name: 'Coral', offer_type: 'free_bet',
    title: 'Bet £5 Get £20 in Free Bets',
    subtitle: 'New customers only.',
    is_featured: false, is_active: true, is_spreadex: false,
    min_deposit_gbp: 5, wagering_req: 1, min_odds: '1/2', expiry_days: 30,
    tc_summary: 'New customers only. 18+. T&Cs apply.',
    ukgc_licence_no: '44548', affiliate_url: 'https://www.coral.co.uk/',
    accent_hex: '004B91', display_order: 6
  }
];

/* ─────────────────────────────────────────
   STATE
───────────────────────────────────────── */
var _oddsMatchId  = null;
var _oddsMarket   = 'h2h';
var _offersFilter = 'all';
var _offersData   = [];

/* ─────────────────────────────────────────
   HELPERS
───────────────────────────────────────── */
function _gcd(a, b) { return b === 0 ? a : _gcd(b, a % b); }

function decimalToFrac(dec) {
  if (!dec || dec <= 1) return 'EVS';
  var n = Math.round((dec - 1) * 100);
  var d = 100;
  var g = _gcd(n, d);
  return (n / g) + '/' + (d / g);
}

function hexToRgba(hex, alpha) {
  var r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!r) return 'rgba(26,23,20,' + alpha + ')';
  return 'rgba(' + parseInt(r[1], 16) + ',' + parseInt(r[2], 16) + ',' + parseInt(r[3], 16) + ',' + alpha + ')';
}

function _esc(str) {
  return String(str || '').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

/* ─────────────────────────────────────────
   1. loadOddsForMatch
───────────────────────────────────────── */
function loadOddsForMatch(matchId) {
  for (var i = 0; i < MOCK_ODDS.length; i++) {
    if (MOCK_ODDS[i].matchId === matchId) return MOCK_ODDS[i];
  }
  return null;
}

/* ─────────────────────────────────────────
   2. renderOddsComparison
───────────────────────────────────────── */
function renderOddsComparison(matchId, market) {
  var container = document.getElementById('odds-comparison-rows');
  if (!container) return;

  var matchData = loadOddsForMatch(matchId);
  if (!matchData) {
    container.innerHTML = '<div class="odds-loading">No odds available.</div>';
    return;
  }

  var rows = (matchData.markets[market] || []).slice();

  /* Pick sort key and display label per market */
  var sortKey, mktLabel;
  if (market === 'h2h')     { sortKey = 'home';  mktLabel = 'Home Win'; }
  else if (market === 'btts')    { sortKey = 'yes';   mktLabel = 'BTTS Yes'; }
  else if (market === 'over_25') { sortKey = 'over';  mktLabel = 'Over 2.5'; }
  else                           { sortKey = 'home';  mktLabel = 'Home Win'; }

  /* Sort descending — best (highest) price first */
  rows.sort(function(a, b) { return (b[sortKey] || 0) - (a[sortKey] || 0); });

  var userAccounts = (typeof userProfile !== 'undefined' && userProfile && userProfile.bookmaker_accounts)
    ? userProfile.bookmaker_accounts : [];

  var html = '';
  rows.forEach(function(row, idx) {
    var isBest     = idx === 0;
    var bookie     = row.bookmaker;
    var licence    = BOOKIE_LICENCES[bookie] || '';
    var hasAccount = userAccounts.indexOf(bookie) !== -1;
    var url        = AFFILIATE_URLS[bookie] || '#';
    var price      = row[sortKey];

    var dot       = isBest ? '<div class="odds-dot-best"></div>' : '<div class="odds-dot-other"></div>';
    var bestLabel = isBest ? '<span class="odds-best-label">Best price</span>' : '';
    var acctBadge = hasAccount
      ? '<span class="odds-acct-badge">✓ Account</span>'
      : '<span class="odds-new-badge">New Customer Offer</span>';
    var priceClass = isBest ? 'best' : (idx < rows.length - 1 ? 'mid' : 'worst');

    html +=
      '<div class="odds-row" onclick="window.open(\'' + _esc(url) + '\',\'_blank\')">' +
        dot +
        '<div class="odds-bookie-wrap">' +
          '<div class="odds-bookie-name">' + _esc(bookie) + bestLabel + acctBadge + '</div>' +
          '<div class="odds-licence">UKGC ' + _esc(licence) + '</div>' +
        '</div>' +
        '<div class="odds-price ' + priceClass + '">' + decimalToFrac(price) + '</div>' +
        '<div class="odds-arrow">›</div>' +
      '</div>';
  });

  container.innerHTML = html || '<div class="odds-loading">No odds for this market.</div>';

  /* Update subtitle showing which selection is being compared */
  var subtitleEl = document.getElementById('odds-market-subtitle');
  if (subtitleEl) subtitleEl.textContent = mktLabel + ' · Best price first';
}

/* ─────────────────────────────────────────
   3. switchOddsMarket
───────────────────────────────────────── */
function switchOddsMarket(market) {
  _oddsMarket = market;
  document.querySelectorAll('.mkt-tab').forEach(function(tab) {
    tab.classList.toggle('active', tab.dataset.market === market);
  });
  renderOddsComparison(_oddsMatchId, market);
}

/* ─────────────────────────────────────────
   4. loadOddsForScreen
───────────────────────────────────────── */
function loadOddsForScreen(matchId) {
  _oddsMatchId = matchId || MOCK_ODDS[0].matchId;
  _oddsMarket  = 'h2h';

  var matchData = loadOddsForMatch(_oddsMatchId);

  /* Populate match title */
  var titleEl = document.getElementById('odds-match-title');
  if (titleEl) {
    titleEl.textContent = matchData
      ? matchData.homeTeam + ' vs ' + matchData.awayTeam + ' · ' + matchData.competition
      : 'Odds Comparison';
  }

  /* Reset market tabs to h2h */
  document.querySelectorAll('.mkt-tab').forEach(function(tab) {
    tab.classList.toggle('active', tab.dataset.market === 'h2h');
  });

  renderOddsComparison(_oddsMatchId, 'h2h');
}

/* ─────────────────────────────────────────
   5. loadOffers
───────────────────────────────────────── */
function loadOffers() {
  var offersContainer = document.getElementById('offer-cards-container');
  if (offersContainer) offersContainer.innerHTML = '<div class="offers-loading">Loading offers…</div>';

  if (!sbClient) {
    _offersData = OFFERS_FALLBACK.slice();
    renderOfferCards(_offersData, _offersFilter);
    return;
  }

  sbClient
    .from('pitchside_offers')
    .select('*')
    .eq('is_active', true)
    .order('display_order', { ascending: true })
    .then(function(result) {
      if (result.error || !result.data || !result.data.length) {
        _offersData = OFFERS_FALLBACK.slice();
      } else {
        _offersData = result.data;
      }
      renderOfferCards(_offersData, _offersFilter);
    });
}

/* ─────────────────────────────────────────
   6. renderOfferCards helpers
───────────────────────────────────────── */
function _termCell(label, val) {
  return '<div class="oc-term">' +
    '<div class="oct-lbl">' + label + '</div>' +
    '<div class="oct-val">' + _esc(val || '—') + '</div>' +
    '</div>';
}

var _OFFER_TYPE_LABELS = {
  welcome_bonus: 'Welcome',
  free_bet:      'Free Bet',
  free_spins:    'Free Spins',
  no_deposit:    'No Deposit',
  cashback:      'Cashback'
};

function _buildFeaturedHtml(offer) {
  var url = _esc(offer.affiliate_url || '#');
  return '<div class="offer-hero" onclick="window.open(\'' + url + '\',\'_blank\')" style="cursor:pointer">' +
    '<div class="oh-glow"></div>' +
    '<div class="oh-eye">Featured Offer · ' + _esc(offer.operator_name) + '</div>' +
    '<div class="oh-title">' + _esc(offer.title) + '</div>' +
    '<div style="font-family:var(--fm);font-size:8px;color:rgba(255,255,255,0.55);margin-top:4px">New Customers Only · 18+</div>' +
    '<div class="oh-btn">Get Offer ↗</div>' +
    '</div>';
}

function _buildCardHtml(offer) {
  var url        = _esc(offer.affiliate_url || '#');
  var color      = '#' + (offer.accent_hex || '1A1714');
  var accent     = 'linear-gradient(90deg,' + color + ',' + color + ')';
  var badgeBg    = hexToRgba(color, 0.1);
  var typeLabel  = _OFFER_TYPE_LABELS[offer.offer_type] || (offer.offer_type || '');
  var minDep     = offer.min_deposit_gbp != null ? '£' + offer.min_deposit_gbp : 'N/A';
  var wagering   = (offer.wagering_req && offer.wagering_req > 0) ? offer.wagering_req + 'x' : 'N/A';
  var expiry     = offer.expiry_days ? offer.expiry_days + ' days' : 'Ongoing';

  var spreadexBanner = offer.is_spreadex
    ? '<div class="spreadex-warning">⚠ Spread betting losses can exceed your initial deposit.</div>' : '';

  var terms = '<div class="oc-terms">' +
    _termCell('Min Deposit', minDep) +
    _termCell('Wagering',    wagering) +
    _termCell('Min Odds',    offer.min_odds) +
    _termCell('Expires',     expiry) +
    '</div>';

  return spreadexBanner +
    '<div class="offer-card">' +
      '<div class="oc-accent" style="background:' + accent + '"></div>' +
      '<div class="oc-body">' +
        '<div class="oc-hdr">' +
          '<div>' +
            '<div class="oc-op">' + _esc(offer.operator_name) + '<span class="oc-new-badge">New Customer</span></div>' +
            '<div class="oc-type">' + _esc(typeLabel) + '</div>' +
          '</div>' +
          '<div class="oc-badge" style="color:' + color + ';background:' + badgeBg + '">' + _esc(typeLabel) + '</div>' +
        '</div>' +
        '<div class="oc-title">' + _esc(offer.title) + '</div>' +
        '<div class="oc-sub">' + _esc(offer.subtitle) + '</div>' +
        terms +
        '<div class="oc-ctas">' +
          '<div class="btn-claim" onclick="window.open(\'' + url + '\',\'_blank\')">Claim Offer ↗</div>' +
          '<div class="btn-rev">T&amp;Cs</div>' +
        '</div>' +
      '</div>' +
      '<div class="oc-foot">' +
        '<span class="oc-tc">' + _esc(offer.tc_summary) + '</span>' +
        '<div class="ukgc"><div class="ukgc-dot"></div>UKGC ' + _esc(offer.ukgc_licence_no) + '</div>' +
      '</div>' +
    '</div>';
}

/* ─────────────────────────────────────────
   7. renderOfferCards
───────────────────────────────────────── */
function renderOfferCards(offers, filter) {
  var featuredEl = document.getElementById('featured-offer-container');
  var cardsEl    = document.getElementById('offer-cards-container');
  if (!cardsEl) return;

  var featured = null;
  var cards    = [];

  (offers || []).forEach(function(offer) {
    if (!offer.is_active) return;
    if (offer.is_featured) { if (!featured) featured = offer; return; }
    if (filter !== 'all' && offer.offer_type !== filter) return;
    cards.push(offer);
  });

  /* Featured hero */
  if (featuredEl) {
    if (featured) {
      featuredEl.innerHTML = _buildFeaturedHtml(featured);
      featuredEl.style.display = '';
    } else {
      featuredEl.style.display = 'none';
    }
  }

  /* Offer cards */
  if (!cards.length) {
    cardsEl.innerHTML = '<div class="offers-loading">No offers in this category right now.</div>';
    return;
  }
  var html = '';
  cards.forEach(function(offer) { html += _buildCardHtml(offer); });
  cardsEl.innerHTML = html;
}

/* ─────────────────────────────────────────
   8. switchOfferFilter
───────────────────────────────────────── */
function switchOfferFilter(filter) {
  _offersFilter = filter;
  document.querySelectorAll('.offer-filter-tab').forEach(function(tab) {
    tab.classList.toggle('active', tab.dataset.filter === filter);
  });
  renderOfferCards(_offersData, filter);
}

/* ─────────────────────────────────────────
   9. initPhaseB
───────────────────────────────────────── */
function initPhaseB() {
  /* Market tab handlers for n10 */
  document.querySelectorAll('.mkt-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      switchOddsMarket(tab.dataset.market);
    });
  });

  /* Offer filter tab handlers for n12 */
  document.querySelectorAll('.offer-filter-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      switchOfferFilter(tab.dataset.filter);
    });
  });

  /* Load offers on startup */
  loadOffers();
}

window.addEventListener('load', function() {
  if (typeof initPhaseB === 'function') initPhaseB();
});
