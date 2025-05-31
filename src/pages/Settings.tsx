
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  Building2, 
  Users, 
  Settings as SettingsIcon, 
  Download, 
  Zap, 
  Shield,
  Crown,
  BookOpen
} from 'lucide-react';
import WorkspaceSettings from '@/components/settings/WorkspaceSettings';
import UserRoleManagement from '@/components/settings/UserRoleManagement';
import AIBehaviorSettings from '@/components/settings/AIBehaviorSettings';
import IntegrationSettings from '@/components/settings/IntegrationSettings';
import ExportDataSettings from '@/components/settings/ExportDataSettings';
import AdminDashboard from '@/components/settings/AdminDashboard';
import OnboardingFlow from '@/components/settings/OnboardingFlow';
import SystemPreferences from '@/components/settings/SystemPreferences';

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState('workspace');
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Mock user role - in real app this would come from auth context
  const userRole = 'admin'; // admin, manager, user

  const settingsSections = [
    {
      id: 'workspace',
      name: 'Workspace',
      icon: Building2,
      description: 'Company settings and configuration',
      enterprise: false
    },
    {
      id: 'users',
      name: 'Users & Roles',
      icon: Users,
      description: 'Manage team members and permissions',
      enterprise: true
    },
    {
      id: 'ai-behavior',
      name: 'AI Behavior',
      icon: SettingsIcon,
      description: 'Customize AI responses and workflows',
      enterprise: false
    },
    {
      id: 'integrations',
      name: 'Integrations',
      icon: Zap,
      description: 'Connect external services and APIs',
      enterprise: false
    },
    {
      id: 'export',
      name: 'Export & Backup',
      icon: Download,
      description: 'Data portability and backup options',
      enterprise: true
    },
    {
      id: 'admin',
      name: 'Admin Dashboard',
      icon: Shield,
      description: 'System administration and monitoring',
      enterprise: true,
      adminOnly: true
    }
  ];

  const availableSections = settingsSections.filter(section => {
    if (section.adminOnly && userRole !== 'admin') return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-600 mt-2">Manage your workspace, integrations, and AI behavior</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowOnboarding(true)}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <BookOpen className="h-4 w-4 mr-2" />
            Setup Guide
          </button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-6 lg:w-fit">
          {availableSections.map((section) => {
            const Icon = section.icon;
            return (
              <TabsTrigger 
                key={section.id} 
                value={section.id}
                className="flex items-center space-x-2"
              >
                <Icon className="h-4 w-4" />
                <span className="hidden lg:inline">{section.name}</span>
                {section.enterprise && (
                  <Crown className="h-3 w-3 text-yellow-500" />
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {/* Settings Sections Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {availableSections.map((section) => {
            const Icon = section.icon;
            return (
              <Card 
                key={section.id}
                className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
                  activeTab === section.id ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setActiveTab(section.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-blue-100 rounded-lg">
                      <Icon className="h-5 w-5 text-blue-600" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <h3 className="font-medium">{section.name}</h3>
                        {section.enterprise && (
                          <Badge variant="secondary" className="text-xs">
                            Enterprise
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{section.description}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Settings Content */}
        <TabsContent value="workspace">
          <WorkspaceSettings />
        </TabsContent>

        <TabsContent value="users">
          <UserRoleManagement />
        </TabsContent>

        <TabsContent value="ai-behavior">
          <AIBehaviorSettings />
        </TabsContent>

        <TabsContent value="integrations">
          <IntegrationSettings />
        </TabsContent>

        <TabsContent value="export">
          <ExportDataSettings />
        </TabsContent>

        <TabsContent value="admin">
          <AdminDashboard />
        </TabsContent>
      </Tabs>

      {/* Onboarding Flow Modal */}
      {showOnboarding && (
        <OnboardingFlow onClose={() => setShowOnboarding(false)} />
      )}

      {/* System Preferences Footer */}
      <SystemPreferences />
    </div>
  );
};

export default Settings;
