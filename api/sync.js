import { createClient } from '@supabase/supabase-js';
import axios from 'axios';

const LEAGUES = [
  39,  // English Premier League
  40,  // English Championship
  41,  // English League One
  42,  // English League Two
  179, // Scottish Premiership
  140, // Spanish La Liga
  135, // Italian Serie A
  78,  // German Bundesliga
  61,  // French Ligue 1
  94,  // Portuguese Primeira Liga
  88,  // Dutch Eredivisie
  203, // Turkish Süper Lig
  307, // Saudi Pro League
  253, // MLS (USA)
  71,  // Brazilian Série A
  2,   // UEFA Champions League
  3,   // UEFA Europa League
  848, // UEFA Conference League
];

const SEASON = 2025;

export default async function handler(req, res) {
  const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY
  );

  const today = new Date().toISOString().split('T')[0];

  let totalSynced = 0;
  let errors = [];

  for (const leagueId of LEAGUES) {
    try {
      const response = await axios.get(
        'https://v3.football.api-sports.io/fixtures',
        {
          params: {
            league: leagueId,
            season: SEASON,
            date: today
          },
          headers: {
            'x-apisports-key': process.env.FOOTBALL_API_KEY,
            'x-apisports-host': 'v3.football.api-sports.io'
          }
        }
      );

      const fixtures = response.data.response;

      if (!fixtures || fixtures.length === 0) continue;

      const rows = fixtures.map(f => ({
        id: f.fixture.id,
        home_team: f.teams.home.name,
        away_team: f.teams.away.name,
        kickoff: f.fixture.date,
        status: f.fixture.status.short,
        competition: f.league.name
      }));

      const { error } = await supabase
        .from('matches')
        .upsert(rows, { onConflict: 'id' });

      if (error) {
        errors.push(`League ${leagueId}: ${error.message}`);
      } else {
        totalSynced += rows.length;
      }

    } catch (err) {
      errors.push(`League ${leagueId}: ${err.message}`);
    }
  }

  res.status(200).json({
    message: "Sync complete",
    date: today,
    total_matches_synced: totalSynced,
    errors: errors
  });
}
