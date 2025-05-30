export const handler = async (event, context) => {
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'
    },
    body: JSON.stringify({
      status: "running",
      message: "Wheels & Wins AI Marketing API",
      timestamp: new Date().toISOString(),
      environment: "netlify-functions"
    })
  };
};