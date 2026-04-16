#!/usr/bin/env node
/**
 * fetch-team-ids.js
 * Fetches real API-Football team IDs for all 8 leagues (season 2024)
 * and writes team-ids.txt with name, id, and badge URL for each team.
 *
 * Usage:  FOOTBALL_API_KEY=your_key node fetch-team-ids.js
 */

const https = require('https');
const fs    = require('fs');

const API_KEY = process.env.FOOTBALL_API_KEY;
if (!API_KEY) {
  console.error('ERROR: FOOTBALL_API_KEY environment variable is not set.');
  process.exit(1);
}

const LEAGUES = [
  { id: 39,  name: 'PREMIER LEAGUE'        },
  { id: 40,  name: 'CHAMPIONSHIP'           },
  { id: 41,  name: 'LEAGUE ONE'             },
  { id: 42,  name: 'LEAGUE TWO'             },
  { id: 179, name: 'SCOTTISH PREMIERSHIP'   },
  { id: 180, name: 'SCOTTISH CHAMPIONSHIP'  },
  { id: 181, name: 'SCOTTISH LEAGUE ONE'    },
  { id: 182, name: 'SCOTTISH LEAGUE TWO'    },
];

function fetchLeague(leagueId) {
  return new Promise(function(resolve, reject) {
    const url = 'https://v3.football.api-sports.io/teams?league=' + leagueId + '&season=2024';
    const options = {
      headers: {
        'x-apisports-key':  API_KEY,
        'x-apisports-host': 'v3.football.api-sports.io'
      }
    };
    https.get(url, options, function(res) {
      var data = '';
      res.on('data', function(chunk) { data += chunk; });
      res.on('end', function() {
        try {
          resolve(JSON.parse(data));
        } catch(e) {
          reject(new Error('JSON parse error for league ' + leagueId + ': ' + e.message));
        }
      });
    }).on('error', reject);
  });
}

async function main() {
  var lines   = [];
  var allRows = [];

  for (var i = 0; i < LEAGUES.length; i++) {
    var lg = LEAGUES[i];
    process.stdout.write('Fetching ' + lg.name + ' (league ' + lg.id + ')… ');

    var json;
    try {
      json = await fetchLeague(lg.id);
    } catch(e) {
      console.log('FAILED — ' + e.message);
      continue;
    }

    if (!json.response || !json.response.length) {
      console.log('No teams returned (check key/quota). Raw: ' + JSON.stringify(json).slice(0,120));
      continue;
    }

    var teams = json.response.map(function(entry) {
      return { name: entry.team.name, id: entry.team.id };
    });

    console.log(teams.length + ' teams');

    var header = '\n// ' + lg.name + ' (league ' + lg.id + ')';
    lines.push(header);
    allRows.push(header);

    teams.forEach(function(t) {
      var badge = 'https://media.api-sports.io/football/teams/' + t.id + '.png';
      var line  = "{ name: '" + t.name + "', id: " + t.id + ", badge: '" + badge + "' }";
      console.log('  ' + line);
      lines.push(line);
      allRows.push("  '" + t.name + "': " + t.id + ',');
    });
  }

  // Write full output to team-ids.txt
  var out = '// API-Football team IDs — fetched ' + new Date().toISOString() + '\n\n';
  out += lines.join('\n') + '\n\n';
  out += '// ── TEAM_IDS object (paste into phase-a-additions-2.js) ──\n';
  out += 'var TEAM_IDS = {\n';
  out += allRows.filter(function(r) { return r.startsWith("  '"); }).join('\n');
  out += '\n};\n';

  fs.writeFileSync('team-ids.txt', out, 'utf8');
  console.log('\n✓ Results written to team-ids.txt');
}

main().catch(function(err) {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
