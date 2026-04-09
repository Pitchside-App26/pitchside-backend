const { createClient } = require('@supabase/supabase-js');
const axios = require('axios');
 
export default async function handler(req, res) {
  const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
 
  const options = {
    method: 'GET',
    url: 'https://v3.football.api-sports.io/fixtures',
    params: { next: '20' }, // Just get the next 20 games globally
    headers: {
      'x-apisports-key': process.env.FOOTBALL_API_KEY,
      'x-apisports-host': 'v3.football.api-sports.io'
    }
  };
 
  try {
    const response = await axios.request(options);
    const fixtures = response.data.response;
 
    // This version is "simpler" to ensure it doesn't skip data
    const { data, error } = await supabase.from('matches').upsert(
      fixtures.map(item => ({
        id: item.fixture.id,
        home_team: item.teams.home.name,
        away_team: item.teams.away.name,
        kickoff: item.fixture.date,
        status: item.fixture.status.short
      }))
    );
 
    if (error) throw error;
 
    res.status(200).json({
      message: 'Sync Successful',
      count: fixtures.length,
      sample: fixtures.length > 0 ? fixtures[0].teams.home.name : 'No data found in API'
    });
  } catch (error) {
    res.status(500).json({ error: error.message, details: error.response?.data });
  }
}
