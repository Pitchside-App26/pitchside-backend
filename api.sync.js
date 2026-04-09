const { createClient } = require('@supabase/supabase-js');
const axios = require('axios');
 
// This function connects to your Supabase and API-Football
export default async function handler(req, res) {
  const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY
  );
 
  const options = {
    method: 'GET',
    url: 'https://v3.football.api-sports.io/fixtures',
    params: {
      league: '39', // Premier League (You can add 30 for Scottish Premiership later!)
      next: '10'    // Get the next 10 matches
    },
    headers: {
      'x-apisports-key': process.env.FOOTBALL_API_KEY,
      'x-apisports-host': 'v3.football.api-sports.io'
    }
  };
 
  try {
    const response = await axios.request(options);
    const fixtures = response.data.response;
 
    const results = await Promise.all(fixtures.map(async (item) => {
      return supabase.from('matches').upsert({
        id: item.fixture.id,
        venue_id: item.fixture.venue.id.toString(),
        home_team: item.teams.home.name,
        away_team: item.teams.away.name,
        kickoff: item.fixture.date,
        status: item.fixture.status.short
      });
    }));
  
    res.status(200).json({ message: 'Sync Successful', count: fixtures.length });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}
 
