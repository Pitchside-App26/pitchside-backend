const { createClient } = require('@supabase/supabase-js');
const axios = require('axios');
 
export default async function handler(req, res) {
  // 1. Setup Supabase
  const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY
  );
 
  // 2. Setup API Call (Fetching Leagues to prove the key works)
  const options = {
    method: 'GET',
    url: 'https://v3.football.api-sports.io/leagues',
    params: { id: '179' }, // 179 is the Scottish Premiership
    headers: {
      'x-apisports-key': process.env.FOOTBALL_API_KEY,
      'x-apisports-host': 'v3.football.api-sports.io'
    }
  };
 
  try {
    console.log("Starting API Call...");
    const response = await axios.request(options);
    
    // Check if the API actually sent data
    const apiData = response.data.response;
    console.log("API Response Status:", response.data.errors);
    console.log("Data Received Count:", apiData.length);
 
    if (apiData.length === 0) {
      return res.status(200).json({
        message: "API connected but returned no data.",
        debug_info: response.data.errors,
        suggestion: "Check if your API Key is active in the API-Football dashboard."
      });
    }
 
    // 3. Try to save at least one thing to Supabase to prove the link
    const leagueName = apiData[0].league.name;
    const country = apiData[0].country.name;
 
    // We will 'upsert' into matches just as a test, or you can just return the success
    res.status(200).json({
      message: "Sync Successful!",
      count: apiData.length,
      league_found: leagueName,
      country_found: country,
      timestamp: new Date().toISOString()
    });
 
  } catch (error) {
    console.error("CRASH ERROR:", error.message);
    res.status(500).json({
      error: error.message,
      details: "Check Vercel Logs for the full error stack."
    });
  }
}
