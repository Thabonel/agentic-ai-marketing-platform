import React, { useState, useEffect } from 'react';
import { 
  Bot, 
  BarChart3, 
  Settings, 
  Users, 
  MessageSquare, 
  PlayCircle, 
  StopCircle, 
  Plus,
  Activity,
  TrendingUp,
  Mail,
  Target,
  Zap,
  CheckCircle,
  AlertCircle,
  Clock,
  DollarSign
} from 'lucide-react';

// Configuration
const API_BASE_URL = 'https://wheels-wins-orchestrator.onrender.com';

const AgentStatusBadge = ({ status }) => {
  const statusConfig = {
    idle: { color: 'bg-gray-500', icon: Clock, text: 'Idle' },
    running: { color: 'bg-green-500', icon: PlayCircle, text: 'Running' },
    error: { color: 'bg-red-500', icon: AlertCircle, text: 'Error' },
    stopped: { color: 'bg-yellow-500', icon: StopCircle, text: 'Stopped' }
  };
  
  const config = statusConfig[status] || statusConfig.idle;
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium text-white ${config.color}`}>
      <Icon className="w-3 h-3 mr-1" />
      {config.text}
    </span>
  );
};

const AgentCard = ({ agent, onChat, onToggle }) => {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <Bot className="w-8 h-8 text-blue-600 mr-3" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{agent.name}</h3>
            <p className="text-sm text-gray-500">{agent.type}</p>
          </div>
        </div>
        <AgentStatusBadge status={agent.status} />
      </div>
      
      <p className="text-gray-600 mb-4">{agent.description}</p>
      
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          Last run: {agent.last_run_at ? new Date(agent.last_run_at).toLocaleString() : 'Never'}
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => onChat(agent)}
            className="px-3 py-1 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition-colors"
          >
            <MessageSquare className="w-4 h-4 inline mr-1" />
            Chat
          </button>
          <button
            onClick={() => onToggle(agent)}
            className={`px-3 py-1 rounded-md text-sm transition-colors ${
              agent.status === 'running' 
                ? 'bg-red-600 text-white hover:bg-red-700' 
                : 'bg-green-600 text-white hover:bg-green-700'
            }`}
          >
            {agent.status === 'running' ? (
              <>
                <StopCircle className="w-4 h-4 inline mr-1" />
                Stop
              </>
            ) : (
              <>
                <PlayCircle className="w-4 h-4 inline mr-1" />
                Start
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

const ChatInterface = ({ agent, onClose }) => {
  const [messages, setMessages] = useState([
    { id: 1, type: 'agent', content: `Hello! I'm ${agent.name}, your ${agent.type} agent. How can I help you today?` }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = { id: Date.now(), type: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Create a task for the agent
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agent.id,
          task_type: 'chat_response',
          input_data: { message: inputMessage }
        })
      });

      if (response.ok) {
        // Simulate agent response
        setTimeout(() => {
          const agentResponse = {
            id: Date.now() + 1,
            type: 'agent',
            content: `I've received your request: "${inputMessage}". I'm processing this and will execute the appropriate marketing automation tasks. Let me analyze your requirements and generate the best strategy.`
          };
          setMessages(prev => [...prev, agentResponse]);
          setIsLoading(false);
        }, 2000);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl h-96 flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center">
            <Bot className="w-6 h-6 text-blue-600 mr-2" />
            <h3 className="text-lg font-semibold">Chat with {agent.name}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map(message => (
            <div
              key={message.id}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                  message.type === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-900'
                }`}
              >
                {message.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-200 text-gray-900 px-4 py-2 rounded-lg">
                <div className="flex items-center">
                  <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full mr-2"></div>
                  Agent is thinking...
                </div>
              </div>
            </div>
          )}
        </div>
        
        <div className="p-4 border-t">
          <div className="flex space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Ask your agent anything..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={sendMessage}
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const CreateAgentModal = ({ onClose, onAgentCreated }) => {
  const [formData, setFormData] = useState({
    name: '',
    type: 'lead_generator',
    description: ''
  });

  const agentTypes = [
    { value: 'lead_generator', label: 'Lead Generator', icon: Users },
    { value: 'content_creator', label: 'Content Creator', icon: Mail },
    { value: 'campaign_manager', label: 'Campaign Manager', icon: Target },
    { value: 'market_researcher', label: 'Market Researcher', icon: BarChart3 }
  ];

  const handleSubmit = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        const newAgent = await response.json();
        onAgentCreated(newAgent);
        onClose();
      }
    } catch (error) {
      console.error('Error creating agent:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">Create New Agent</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>
        
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({...formData, type: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {agentTypes.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows="3"
            />
          </div>
          
          <div className="flex justify-end space-x-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Create Agent
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [agents, setAgents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showCreateAgent, setShowCreateAgent] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [agentsRes, tasksRes, analyticsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/agents`),
        fetch(`${API_BASE_URL}/tasks?limit=50`),
        fetch(`${API_BASE_URL}/analytics/dashboard`)
      ]);

      if (agentsRes.ok) setAgents(await agentsRes.json());
      if (tasksRes.ok) setTasks(await tasksRes.json());
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching data:', error);
      setLoading(false);
    }
  };

  const handleToggleAgent = async (agent) => {
    try {
      const newStatus = agent.status === 'running' ? 'idle' : 'running';
      await fetch(`${API_BASE_URL}/agents/${agent.id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      fetchData();
    } catch (error) {
      console.error('Error toggling agent:', error);
    }
  };

  const StatsCard = ({ title, value, icon: Icon, color = 'blue' }) => (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <Icon className={`w-8 h-8 text-${color}-600`} />
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">Loading AI Marketing Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Zap className="w-8 h-8 text-blue-600 mr-3" />
              <h1 className="text-xl font-bold text-gray-900">Wheels Wins AI Marketing</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowCreateAgent(true)}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center"
              >
                <Plus className="w-4 h-4 mr-2" />
                New Agent
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
              { id: 'agents', label: 'Agents', icon: Bot },
              { id: 'campaigns', label: 'Campaigns', icon: Target },
              { id: 'analytics', label: 'Analytics', icon: TrendingUp }
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center px-3 py-4 text-sm font-medium border-b-2 ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatsCard 
                title="Active Agents" 
                value={agents.filter(a => a.status === 'running').length} 
                icon={Bot} 
                color="green" 
              />
              <StatsCard 
                title="Total Tasks" 
                value={tasks.length} 
                icon={Activity} 
                color="blue" 
              />
              <StatsCard 
                title="Completed Today" 
                value={tasks.filter(t => t.status === 'completed').length} 
                icon={CheckCircle} 
                color="green" 
              />
              <StatsCard 
                title="Active Campaigns" 
                value={analytics?.campaigns?.active || 0} 
                icon={Target} 
                color="purple" 
              />
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-lg shadow-md">
              <div className="px-6 py-4 border-b">
                <h2 className="text-lg font-semibold text-gray-900">Recent Agent Activity</h2>
              </div>
              <div className="p-6">
                <div className="space-y-4">
                  {tasks.slice(0, 5).map(task => (
                    <div key={task.id} className="flex items-center justify-between py-2">
                      <div className="flex items-center">
                        <div className={`w-2 h-2 rounded-full mr-3 ${
                          task.status === 'completed' ? 'bg-green-500' :
                          task.status === 'running' ? 'bg-blue-500' :
                          task.status === 'failed' ? 'bg-red-500' : 'bg-gray-500'
                        }`}></div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{task.task_type}</p>
                          <p className="text-xs text-gray-500">Agent {task.agent_id}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500">
                          {task.started_at ? new Date(task.started_at).toLocaleTimeString() : 'Pending'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-gray-900">AI Marketing Agents</h2>
              <p className="text-gray-600">{agents.length} agents configured</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {agents.map(agent => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onChat={setSelectedAgent}
                  onToggle={handleToggleAgent}
                />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'campaigns' && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Campaign Management</h2>
            <div className="text-center py-12">
              <Target className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Campaign Builder Coming Soon</h3>
              <p className="text-gray-600">Advanced campaign creation and management features will be available here.</p>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Performance Analytics</h2>
            <div className="text-center py-12">
              <TrendingUp className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Advanced Analytics Coming Soon</h3>
              <p className="text-gray-600">Detailed performance metrics and insights will be displayed here.</p>
            </div>
          </div>
        )}
      </main>

      {/* Modals */}
      {selectedAgent && (
        <ChatInterface
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
        />
      )}

      {showCreateAgent && (
        <CreateAgentModal
          onClose={() => setShowCreateAgent(false)}
          onAgentCreated={(agent) => {
            setAgents([...agents, agent]);
            fetchData();
          }}
        />
      )}
    </div>
  );
};

export default Dashboard;
