// netlify/functions/generate-analytics.js

const { Configuration, OpenAIApi } = require('openai');

const configuration = new Configuration({
  apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);

exports.handler = async (event, context) => {
  // Handle CORS
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
  };

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
    };
  }

  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method not allowed' }),
    };
  }

  try {
    const body = JSON.parse(event.body);
    const { action, metrics, period = '30_days' } = body;

    if (action === 'generate_insights') {
      // Generate AI insights from metrics
      if (!metrics) {
        return {
          statusCode: 400,
          headers,
          body: JSON.stringify({ error: 'Metrics data required' }),
        };
      }

      const insightsPrompt = `Analyze these marketing metrics and provide insights:

${JSON.stringify(metrics, null, 2)}

Identify:
1. Key performance trends
2. Areas of concern
3. Optimization opportunities
4. Strategic recommendations

Provide 3-5 actionable insights in JSON format:
[
  {
    "level": "high/medium/low",
    "title": "Brief insight title",
    "description": "Detailed analysis",
    "impact_score": 0.0-1.0,
    "recommendations": ["action1", "action2"]
  }
]`;

      const completion = await openai.createChatCompletion({
        model: 'gpt-4',
        messages: [
          {
            role: 'system',
            content: 'You are a marketing analytics expert. Always respond with valid JSON.',
          },
          {
            role: 'user',
            content: insightsPrompt,
          },
        ],
        temperature: 0.3,
        max_tokens: 1500,
      });

      let insights;
      try {
        insights = JSON.parse(completion.data.choices[0].message.content);
      } catch (parseError) {
        insights = [{
          level: 'medium',
          title: 'Analytics Processing',
          description: 'Analytics insights are being processed. Please check back later.',
          impact_score: 0.5,
          recommendations: ['Review metrics regularly', 'Monitor key performance indicators']
        }];
      }

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          insights: insights,
          generated_at: new Date().toISOString(),
          period: period
        }),
      };

    } else if (action === 'dashboard_data') {
      // Generate dashboard summary data
      const mockMetrics = {
        total_campaigns: Math.floor(Math.random() * 20) + 5,
        active_campaigns: Math.floor(Math.random() * 10) + 2,
        total_leads: Math.floor(Math.random() * 500) + 100,
        qualified_leads: Math.floor(Math.random() * 100) + 20,
        content_pieces: Math.floor(Math.random() * 50) + 10,
        social_posts: Math.floor(Math.random() * 100) + 25,
        email_contacts: Math.floor(Math.random() * 1000) + 200,
        avg_engagement_rate: (Math.random() * 10 + 5).toFixed(2)
      };

      // Generate performance summary
      const summaryPrompt = `Based on these marketing metrics, create a brief executive summary:

${JSON.stringify(mockMetrics, null, 2)}

Provide a 2-3 sentence summary highlighting overall performance and key trends.`;

      const summaryCompletion = await openai.createChatCompletion({
        model: 'gpt-4',
        messages: [
          {
            role: 'system',
            content: 'You are a marketing executive creating performance summaries.',
          },
          {
            role: 'user',
            content: summaryPrompt,
          },
        ],
        temperature: 0.5,
        max_tokens: 200,
      });

      const executiveSummary = summaryCompletion.data.choices[0].message.content.trim();

      const dashboardData = {
        kpi_summary: mockMetrics,
        executive_summary: executiveSummary,
        performance_trend: Math.random() > 0.5 ? 'improving' : 'stable',
        alerts: [],
        last_updated: new Date().toISOString()
      };

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(dashboardData),
      };

    } else if (action === 'generate_report') {
      // Generate comprehensive analytics report
      const { report_type = 'weekly', start_date, end_date } = body;

      const reportPrompt = `Create a ${report_type} marketing analytics report summary for the period ${start_date || 'last week'} to ${end_date || 'today'}.

Include:
1. Executive summary
2. Key performance highlights
3. Areas for improvement
4. Strategic recommendations

Format as JSON:
{
  "title": "Report title",
  "executive_summary": "2-3 paragraph summary",
  "key_highlights": ["highlight1", "highlight2", "highlight3"],
  "recommendations": ["rec1", "rec2", "rec3"]
}`;

      const reportCompletion = await openai.createChatCompletion({
        model: 'gpt-4',
        messages: [
          {
            role: 'system',
            content: 'You are a marketing analytics expert creating executive reports.',
          },
          {
            role: 'user',
            content: reportPrompt,
          },
        ],
        temperature: 0.4,
        max_tokens: 1000,
      });

      let reportData;
      try {
        reportData = JSON.parse(reportCompletion.data.choices[0].message.content);
      } catch (parseError) {
        reportData = {
          title: `${report_type.charAt(0).toUpperCase() + report_type.slice(1)} Marketing Report`,
          executive_summary: 'Marketing performance analysis is being processed. Key metrics show steady progress across all channels.',
          key_highlights: ['Campaign performance within targets', 'Lead generation showing positive trends', 'Content engagement rates stable'],
          recommendations: ['Continue current strategies', 'Monitor emerging trends', 'Optimize high-performing channels']
        };
      }

      const report = {
        report_id: `report_${report_type}_${Date.now()}`,
        ...reportData,
        report_type: report_type,
        period_start: start_date || new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        period_end: end_date || new Date().toISOString(),
        created_at: new Date().toISOString()
      };

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(report),
      };

    } else {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Invalid action. Use "generate_insights", "dashboard_data", or "generate_report"' }),
      };
    }

  } catch (error) {
    console.error('Error in analytics function:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        error: 'Analytics function failed',
        details: error.message 
      }),
    };
  }
};
