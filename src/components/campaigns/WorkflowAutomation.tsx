
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { behaviorTracker } from '@/lib/behavior-tracker';
import { Zap, Copy, Play, Pause, Target, Calendar } from 'lucide-react';

interface Campaign {
  id: string;
  name: string;
  type: string;
  status: string;
  performance?: {
    successScore: number;
  };
}

interface WorkflowAutomationProps {
  campaigns: Campaign[];
  onCampaignUpdate: () => void;
}

const WorkflowAutomation: React.FC<WorkflowAutomationProps> = ({ campaigns, onCampaignUpdate }) => {
  const quickActions = [
    {
      id: 'duplicate-best',
      title: 'Duplicate Best Performer',
      description: 'Create a copy of your highest performing campaign',
      icon: Copy,
      color: 'blue',
      enabled: campaigns.length > 0
    },
    {
      id: 'launch-optimal',
      title: 'Launch at Optimal Time',
      description: 'Schedule next campaign for your best performing time slot',
      icon: Calendar,
      color: 'green',
      enabled: true
    },
    {
      id: 'optimize-budget',
      title: 'Optimize Budget',
      description: 'Automatically adjust budgets based on performance',
      icon: Target,
      color: 'purple',
      enabled: campaigns.some(c => c.status === 'active')
    },
    {
      id: 'pause-underperforming',
      title: 'Pause Underperformers',
      description: 'Automatically pause campaigns below threshold',
      icon: Pause,
      color: 'orange',
      enabled: campaigns.some(c => c.status === 'active')
    },
    {
      id: 'quick-launch',
      title: 'Quick Launch Similar',
      description: 'Launch a campaign using proven templates',
      icon: Zap,
      color: 'indigo',
      enabled: true
    },
    {
      id: 'boost-performing',
      title: 'Boost Top Performers',
      description: 'Increase budget on campaigns exceeding targets',
      icon: Play,
      color: 'emerald',
      enabled: campaigns.some(c => c.performance?.successScore && c.performance.successScore > 80)
    }
  ];

  const handleQuickAction = (actionId: string) => {
    behaviorTracker.trackAction('execution', 'workflow_automation', {
      actionId,
      campaignCount: campaigns.length
    });
    
    // Simulate action execution
    console.log(`Executing quick action: ${actionId}`);
    
    // In a real implementation, this would trigger the actual automation
    setTimeout(() => {
      onCampaignUpdate();
    }, 1000);
  };

  const getColorClasses = (color: string) => {
    const colors = {
      blue: 'bg-blue-50 border-blue-200 text-blue-800 hover:bg-blue-100',
      green: 'bg-green-50 border-green-200 text-green-800 hover:bg-green-100',
      purple: 'bg-purple-50 border-purple-200 text-purple-800 hover:bg-purple-100',
      orange: 'bg-orange-50 border-orange-200 text-orange-800 hover:bg-orange-100',
      indigo: 'bg-indigo-50 border-indigo-200 text-indigo-800 hover:bg-indigo-100',
      emerald: 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100'
    };
    return colors[color as keyof typeof colors] || colors.blue;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Zap className="h-5 w-5 text-purple-600" />
          <span>Workflow Automation</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon;
            const colorClasses = getColorClasses(action.color);
            
            return (
              <button
                key={action.id}
                onClick={() => handleQuickAction(action.id)}
                disabled={!action.enabled}
                className={`${colorClasses} border rounded-lg p-4 text-left transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <div className="flex items-start space-x-3">
                  <Icon className="h-5 w-5 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="font-medium mb-1">{action.title}</h4>
                    <p className="text-sm opacity-80">{action.description}</p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-6 pt-4 border-t">
          <h4 className="font-medium text-gray-900 mb-3">Automation Insights</h4>
          <div className="space-y-2 text-sm text-gray-600">
            <p>• Your campaigns perform 34% better when launched Tuesday-Thursday</p>
            <p>• Budget optimization typically increases ROI by 28%</p>
            <p>• Quick launch templates save you an average of 1.5 hours</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default WorkflowAutomation;
