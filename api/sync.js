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
  console.log(`[sync] START — date=${today} season=${SEASON} leagues=${LEAGUES.length}`);

  // Log env var presence (never log actual values)
  console.log(`[sync] ENV CHECK — FOOTBALL_API_KEY=${process.env.FOOTBALL_API_KEY ? 'SET' : 'MISSING'} SUPABASE_URL=${process.env.SUPABASE_URL ? 'SET' : 'MISSING'} SUPABASE_SERVICE_ROLE_KEY=${process.env.SUPABASE_SERVICE_ROLE_KEY ? 'SET' : 'MISSING'}`);

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

      const httpStatus = response.status;
      const rawFixtureCount = Array.isArray(response.data.response) ? response.data.response.length : 'non-array';
      const apiErrors = response.data.errors;
      const apiResultsCount = response.data.results;
      // Approximate response size from JSON serialisation
      const responseSize = JSON.stringify(response.data).length;

      console.log(`[sync] league=${leagueId} http=${httpStatus} api_results=${apiResultsCount} fixture_count=${rawFixtureCount} response_bytes=${responseSize} api_errors=${JSON.stringify(apiErrors)}`);

      const fixtures = response.data.response;

      if (!fixtures || fixtures.length === 0) {
        console.log(`[sync] league=${leagueId} — no fixtures for ${today}, skipping upsert`);
        continue;
      }

      const rows = fixtures.map(f => ({
        id: f.fixture.id,
        home_team: f.teams.home.name,
        away_team: f.teams.away.name,
        kickoff: f.fixture.date,
        status: f.fixture.status.short,
        competition: f.league.name
      }));

      const { error, data: upsertData, count } = await supabase
        .from('matches')
        .upsert(rows, { onConflict: 'id', count: 'exact' });

      if (error) {
        console.log(`[sync] league=${leagueId} UPSERT ERROR — ${error.message} code=${error.code}`);
        errors.push(`League ${leagueId}: ${error.message}`);
      } else {
        console.log(`[sync] league=${leagueId} UPSERT OK — rows_submitted=${rows.length} rows_affected=${count ?? 'unknown'}`);
        totalSynced += rows.length;
      }

    } catch (err) {
      // Capture axios error details if available
      const axiosStatus = err.response ? err.response.status : 'no_response';
      const axiosBody = err.response ? JSON.stringify(err.response.data).slice(0, 300) : 'n/a';
      console.log(`[sync] league=${leagueId} EXCEPTION — ${err.message} http_status=${axiosStatus} body=${axiosBody}`);
      errors.push(`League ${leagueId}: ${err.message}`);
    }
  }

  console.log(`[sync] DONE — total_synced=${totalSynced} error_count=${errors.length} errors=${JSON.stringify(errors)}`);

  res.status(200).json({
    message: "Sync complete",
    date: today,
    total_matches_synced: totalSynced,
    errors: errors
  });
}
