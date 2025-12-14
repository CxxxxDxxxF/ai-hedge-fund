import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useNodeContext } from '@/contexts/node-context';
import { flowService } from '@/services/flow-service';
import { api } from '@/services/api';
import { API_BASE_URL } from '@/config/api';
import { extractBaseAgentKey } from '@/data/node-mappings';
import { 
  Activity, BarChart3, Brain, Briefcase, CheckCircle2, Clock, DollarSign, 
  FileText, Play, TrendingUp, TrendingDown, Users, Zap, Target, AlertCircle,
  BookOpen, Lightbulb, XCircle, ArrowRight, Calendar, Filter, Building2,
  Award, Shield, Calculator, Globe, ClipboardCheck, LucideIcon
} from 'lucide-react';
import { 
  DEPARTMENTS, assignAgentRole, getDepartmentColorClass, getRankColor,
  Rank, Authority, AgentRole, Department
} from '@/data/departments';
import { useEffect, useState, useCallback } from 'react';
import { Flow } from '@/types/flow';
import { Agent } from '@/data/agents';
import { BacktestRequest, GraphNode, GraphEdge, AgentModelConfig } from '@/services/types';
import { AutomatedTestingPanel } from './automated-testing-panel';
import { StrategyMetricsPanel } from './strategy-metrics-panel';

interface EnhancedDashboardProps {
  className?: string;
}

interface BacktestResult {
  id: number;
  flow_id: number;
  status: string;
  started_at?: string;
  completed_at?: string;
  performance_metrics?: {
    sharpe_ratio?: number;
    sortino_ratio?: number;
    max_drawdown?: number;
    total_return?: number;
    win_rate?: number;
  };
  request_data?: any;
  notes?: string;
  is_breakthrough?: boolean;
  is_loss?: boolean;
}

interface StrategyComparison {
  flow_id: number;
  flow_name: string;
  avg_sharpe: number;
  avg_return: number;
  max_drawdown: number;
  win_rate: number;
  total_tests: number;
  best_result?: BacktestResult;
  worst_result?: BacktestResult;
}

interface AgentPerformance {
  agent_key: string;
  agent_name: string;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  avg_contribution: number;
  best_performance?: number;
  worst_performance?: number;
  last_active?: string;
  status: 'IDLE' | 'IN_PROGRESS' | 'COMPLETE' | 'ERROR';
  current_ticker?: string;
  performance_trend: 'improving' | 'declining' | 'stable' | 'unknown';
  win_rate: number;
  role?: AgentRole;
}

interface DepartmentPerformance {
  department: Department;
  agents: AgentPerformance[];
  total_runs: number;
  avg_performance: number;
  win_rate: number;
  top_performer?: AgentPerformance;
  needs_attention?: AgentPerformance[];
}

export function EnhancedDashboard({ className }: EnhancedDashboardProps) {
  const nodeContext = useNodeContext();
  const [isProcessing, setIsProcessing] = useState(false);
  
  const [flows, setFlows] = useState<Flow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [backtestHistory, setBacktestHistory] = useState<BacktestResult[]>([]);
  const [strategyComparisons, setStrategyComparisons] = useState<StrategyComparison[]>([]);
  const [breakthroughs, setBreakthroughs] = useState<BacktestResult[]>([]);
  const [losses, setLosses] = useState<BacktestResult[]>([]);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformance[]>([]);
  const [departmentPerformance, setDepartmentPerformance] = useState<DepartmentPerformance[]>([]);
  const [selectedDepartment, setSelectedDepartment] = useState<Department | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Quick backtest form
  const [quickBacktest, setQuickBacktest] = useState({
    tickers: 'AAPL,MSFT,NVDA',
    startDate: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
    initialCapital: '100000',
  });
  
  // Create a default graph structure with all agents for dashboard runs
  const createDefaultGraph = useCallback(() => {
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];
    
    // Create nodes for all agents
    if (agents.length > 0) {
      agents.forEach((agent, index) => {
        const nodeId = `${agent.key}_${Date.now()}_${index}`;
        nodes.push({
          id: nodeId,
          type: 'agent-node',
          data: {
            name: agent.display_name,
            description: agent.description,
          },
          position: { x: 100 + (index % 3) * 200, y: 100 + Math.floor(index / 3) * 150 },
        });
        
        // Connect all agents in a simple chain (or you could make it more sophisticated)
        if (index > 0) {
          const prevNodeId = nodes[nodes.length - 2].id;
          edges.push({
            id: `edge_${prevNodeId}_${nodeId}`,
            source: prevNodeId,
            target: nodeId,
          });
        }
      });
    }
    
    return { nodes, edges };
  }, [agents]);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 5000);
    return () => clearInterval(interval);
  }, [flows.length]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [flowsData, agentsData] = await Promise.all([
        flowService.getFlows(),
        api.getAgents(),
      ]);
      setFlows(flowsData);
      setAgents(agentsData);
      
      // Set flows first, then load history
      setFlows(flowsData);
      
      // Load backtest history for all flows (after flows are set)
      await loadBacktestHistory(flowsData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadBacktestHistory = async (flowsToLoad?: Flow[]) => {
    try {
      const allResults: BacktestResult[] = [];
      
      // Use provided flows or state flows
      const currentFlows = flowsToLoad || flows;
      
      for (const flow of currentFlows) {
        try {
          const response = await fetch(`${API_BASE_URL}/flows/${flow.id}/runs?limit=100`);
          if (response.ok) {
            const runs = await response.json();
            const backtests = runs
              .filter((run: any) => run.status === 'COMPLETED' && run.request_data?.start_date)
              .map((run: any) => ({
                ...run,
                flow_name: flow.name,
              }));
            allResults.push(...backtests);
          }
        } catch (err) {
          console.warn(`Failed to load runs for flow ${flow.id}:`, err);
        }
      }
      
      // Sort by completed_at descending
      allResults.sort((a, b) => {
        const dateA = a.completed_at ? new Date(a.completed_at).getTime() : 0;
        const dateB = b.completed_at ? new Date(b.completed_at).getTime() : 0;
        return dateB - dateA;
      });
      
      setBacktestHistory(allResults);
      
      // Separate breakthroughs and losses
      const breakthroughsList = allResults.filter(r => 
        r.performance_metrics?.sharpe_ratio && r.performance_metrics.sharpe_ratio > 1.5
      );
      const lossesList = allResults.filter(r => 
        r.performance_metrics?.max_drawdown && r.performance_metrics.max_drawdown > 0.2
      );
      
      setBreakthroughs(breakthroughsList.slice(0, 10));
      setLosses(lossesList.slice(0, 10));
      
      // Calculate strategy comparisons after history is loaded
      calculateStrategyComparisons();
      
      // Calculate agent performance
      calculateAgentPerformance(allResults);
    } catch (err) {
      console.error('Failed to load backtest history:', err);
    }
  };

  const calculateAgentPerformance = (results: BacktestResult[]) => {
    if (results.length === 0 || agents.length === 0) {
      setAgentPerformance([]);
      return;
    }

    const agentStats = new Map<string, {
      total_runs: number;
      successful_runs: number;
      failed_runs: number;
      performances: number[];
      last_active?: string;
    }>();

    // Initialize all agents
    agents.forEach(agent => {
      agentStats.set(agent.key, {
        total_runs: 0,
        successful_runs: 0,
        failed_runs: 0,
        performances: [],
      });
    });

    // Process results to extract agent performance
    results.forEach(result => {
      // Extract agent signals from request_data or result data
      const analystSignals = result.request_data?.analyst_signals || {};
      const performance = result.performance_metrics?.sharpe_ratio || 0;
      
      Object.keys(analystSignals).forEach(agentKey => {
        const baseKey = extractBaseAgentKey(agentKey);
        const stats = agentStats.get(baseKey);
        if (stats) {
          stats.total_runs++;
          if (performance > 0) {
            stats.successful_runs++;
            stats.performances.push(performance);
          } else if (performance < -0.5) {
            stats.failed_runs++;
          }
          if (result.completed_at) {
            const resultDate = new Date(result.completed_at);
            const lastDate = stats.last_active ? new Date(stats.last_active) : new Date(0);
            if (resultDate > lastDate) {
              stats.last_active = result.completed_at;
            }
          }
        }
      });
    });

      // Get current agent status from node context (use default flow)
      const agentNodes = nodeContext.getAgentNodeDataForFlow('default') || {};

      // Build performance array with roles
      const performanceArray: AgentPerformance[] = agents.map(agent => {
        const role = assignAgentRole(agent);
      const stats = agentStats.get(agent.key) || {
        total_runs: 0,
        successful_runs: 0,
        failed_runs: 0,
        performances: [],
      };

      const avgPerformance = stats.performances.length > 0
        ? stats.performances.reduce((a, b) => a + b, 0) / stats.performances.length
        : 0;

      const bestPerformance = stats.performances.length > 0
        ? Math.max(...stats.performances)
        : undefined;

      const worstPerformance = stats.performances.length > 0
        ? Math.min(...stats.performances)
        : undefined;

      // Determine trend (simplified - compare recent vs older)
      const recentPerf = stats.performances.slice(-3);
      const olderPerf = stats.performances.slice(-6, -3);
      let trend: 'improving' | 'declining' | 'stable' | 'unknown' = 'unknown';
      if (recentPerf.length > 0 && olderPerf.length > 0) {
        const recentAvg = recentPerf.reduce((a, b) => a + b, 0) / recentPerf.length;
        const olderAvg = olderPerf.reduce((a, b) => a + b, 0) / olderPerf.length;
        if (recentAvg > olderAvg + 0.2) trend = 'improving';
        else if (recentAvg < olderAvg - 0.2) trend = 'declining';
        else trend = 'stable';
      }

      // Get current status from node context
      const matchingNodeId = Object.keys(agentNodes).find(nodeId => 
        extractBaseAgentKey(nodeId) === agent.key
      );
      const nodeData = matchingNodeId ? agentNodes[matchingNodeId] : null;

      return {
        agent_key: agent.key,
        agent_name: agent.display_name,
        total_runs: stats.total_runs,
        successful_runs: stats.successful_runs,
        failed_runs: stats.failed_runs,
        avg_contribution: avgPerformance,
        best_performance: bestPerformance,
        worst_performance: worstPerformance,
        last_active: stats.last_active,
        status: (nodeData?.status as any) || 'IDLE',
        current_ticker: nodeData?.ticker || undefined,
        performance_trend: trend,
        win_rate: stats.total_runs > 0 ? stats.successful_runs / stats.total_runs : 0,
        role,
      };
    });

    // Sort by performance (best first)
    performanceArray.sort((a, b) => b.avg_contribution - a.avg_contribution);
    setAgentPerformance(performanceArray);

    // Calculate department performance
    calculateDepartmentPerformance(performanceArray);
  };

  const calculateDepartmentPerformance = (agentPerf: AgentPerformance[]) => {
    const deptMap = new Map<string, AgentPerformance[]>();

    // Group agents by department
    agentPerf.forEach(agent => {
      if (agent.role) {
        const deptId = agent.role.department.id;
        if (!deptMap.has(deptId)) {
          deptMap.set(deptId, []);
        }
        deptMap.get(deptId)!.push(agent);
      }
    });

    // Calculate metrics for each department
    const deptPerformance: DepartmentPerformance[] = DEPARTMENTS.map(dept => {
      const deptAgents = deptMap.get(dept.id) || [];
      
      if (deptAgents.length === 0) {
        return {
          department: dept,
          agents: [],
          total_runs: 0,
          avg_performance: 0,
          win_rate: 0,
        };
      }

      const totalRuns = deptAgents.reduce((sum, a) => sum + a.total_runs, 0);
      const avgPerformance = deptAgents.length > 0
        ? deptAgents.reduce((sum, a) => sum + a.avg_contribution, 0) / deptAgents.length
        : 0;
      const totalWins = deptAgents.reduce((sum, a) => sum + a.successful_runs, 0);
      const winRate = totalRuns > 0 ? totalWins / totalRuns : 0;

      const topPerformer = deptAgents.reduce((best, current) => {
        return (current.avg_contribution > (best?.avg_contribution || -Infinity)) ? current : best;
      }, deptAgents[0]);

      const needsAttention = deptAgents
        .filter(a => a.avg_contribution < 0 || a.win_rate < 0.3)
        .sort((a, b) => a.avg_contribution - b.avg_contribution)
        .slice(0, 3);

      return {
        department: dept,
        agents: deptAgents,
        total_runs: totalRuns,
        avg_performance: avgPerformance,
        win_rate: winRate,
        top_performer: topPerformer,
        needs_attention: needsAttention.length > 0 ? needsAttention : undefined,
      };
    });

    // Sort by average performance
    deptPerformance.sort((a, b) => b.avg_performance - a.avg_performance);
    setDepartmentPerformance(deptPerformance);
  };

  const calculateStrategyComparisons = () => {
    if (backtestHistory.length === 0 || flows.length === 0) {
      setStrategyComparisons([]);
      return;
    }
    
    const comparisons: StrategyComparison[] = [];
    
    // Group results by flow
    const resultsByFlow = new Map<number, BacktestResult[]>();
    backtestHistory.forEach(result => {
      if (!resultsByFlow.has(result.flow_id)) {
        resultsByFlow.set(result.flow_id, []);
      }
      resultsByFlow.get(result.flow_id)!.push(result);
    });
    
    // Calculate metrics for each flow
    resultsByFlow.forEach((results, flowId) => {
      const flow = flows.find(f => f.id === flowId);
      if (!flow || results.length === 0) return;
      
      const sharpeRatios = results
        .map(r => r.performance_metrics?.sharpe_ratio)
        .filter((v): v is number => v !== undefined);
      const returns = results
        .map(r => r.performance_metrics?.total_return)
        .filter((v): v is number => v !== undefined);
      const drawdowns = results
        .map(r => r.performance_metrics?.max_drawdown)
        .filter((v): v is number => v !== undefined);
      
      const avgSharpe = sharpeRatios.length > 0 
        ? sharpeRatios.reduce((a, b) => a + b, 0) / sharpeRatios.length 
        : 0;
      const avgReturn = returns.length > 0
        ? returns.reduce((a, b) => a + b, 0) / returns.length
        : 0;
      const maxDrawdown = drawdowns.length > 0
        ? Math.max(...drawdowns)
        : 0;
      
      const bestResult = results.reduce((best, current) => {
        const bestSharpe = best.performance_metrics?.sharpe_ratio || 0;
        const currentSharpe = current.performance_metrics?.sharpe_ratio || 0;
        return currentSharpe > bestSharpe ? current : best;
      }, results[0]);
      
      const worstResult = results.reduce((worst, current) => {
        const worstDrawdown = worst.performance_metrics?.max_drawdown || 0;
        const currentDrawdown = current.performance_metrics?.max_drawdown || 0;
        return currentDrawdown > worstDrawdown ? current : worst;
      }, results[0]);
      
      comparisons.push({
        flow_id: flowId,
        flow_name: flow.name,
        avg_sharpe: avgSharpe,
        avg_return: avgReturn,
        max_drawdown: maxDrawdown,
        win_rate: sharpeRatios.filter(s => s > 1.0).length / sharpeRatios.length,
        total_tests: results.length,
        best_result: bestResult,
        worst_result: worstResult,
      });
    });
    
    // Sort by average Sharpe ratio
    comparisons.sort((a, b) => b.avg_sharpe - a.avg_sharpe);
    setStrategyComparisons(comparisons);
  };

  const handleQuickBacktest = async () => {
    // Parse tickers from input
    const tickerList = quickBacktest.tickers
      .split(',')
      .map(t => t.trim())
      .filter(t => t !== '');
    
    if (tickerList.length === 0) {
      alert('Please enter at least one ticker symbol');
      return;
    }
    
    setIsProcessing(true);
    
    // Always create default graph with all agents
    const defaultGraph = createDefaultGraph();
    const graphNodes = defaultGraph.nodes;
    const graphEdges = defaultGraph.edges;
    
    // Use default models for all agents
    const agentModels = graphNodes.map(node => ({
      agent_id: node.id,
      model_name: undefined,
      model_provider: undefined,
    }));
    
    // Use a session ID for dashboard runs
    const sessionId = `dashboard-${Date.now()}`;
    
    const backtestRequest: BacktestRequest = {
      tickers: tickerList,
      graph_nodes: graphNodes,
      graph_edges: graphEdges,
      agent_models: agentModels,
      start_date: quickBacktest.startDate,
      end_date: quickBacktest.endDate,
      initial_capital: parseFloat(quickBacktest.initialCapital) || 100000,
    };
    
    // Use the backtest API directly
    const { backtestApi } = await import('@/services/backtest-api');
    backtestApi.runBacktest(backtestRequest, nodeContext, sessionId);
    
    // Monitor for completion
    const checkInterval = setInterval(() => {
      const outputData = nodeContext.getOutputNodeDataForFlow(sessionId);
      const agentData = nodeContext.getAgentNodeDataForFlow(sessionId);
      const backtestAgent = agentData?.['backtest'];
      
      if (backtestAgent?.status === 'COMPLETE' || backtestAgent?.status === 'ERROR') {
        clearInterval(checkInterval);
        setIsProcessing(false);
      }
    }, 1000);
    
    // Timeout after 10 minutes
    setTimeout(() => {
      clearInterval(checkInterval);
      setIsProcessing(false);
    }, 10 * 60 * 1000);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'IN_PROGRESS': return 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50';
      case 'COMPLETED': return 'bg-green-500/20 text-green-500 border-green-500/50';
      case 'ERROR': return 'bg-red-500/20 text-red-500 border-red-500/50';
      default: return 'bg-gray-500/20 text-gray-500 border-gray-500/50';
    }
  };

  const getDepartmentIcon = (iconName: string): LucideIcon => {
    const iconMap: Record<string, LucideIcon> = {
      DollarSign,
      TrendingUp,
      BarChart3,
      Calculator,
      Shield,
      Globe,
      ClipboardCheck,
    };
    return iconMap[iconName] || Building2;
  };

  return (
    <div className={`p-6 space-y-6 overflow-y-auto h-full ${className}`}>
      {/* Header with Quick Actions */}
      <div className="flex items-center justify-between animate-in fade-in slide-in-from-top-4 duration-500">
        <div>
          <h1 className="text-3xl font-bold text-primary animate-in fade-in slide-in-from-left-4 duration-700">
            Hedge Fund Command Center
          </h1>
          <p className="text-sm text-muted-foreground mt-1 animate-in fade-in slide-in-from-left-4 duration-700 delay-100">
            Backtesting & Strategy Optimization Dashboard
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge 
            variant="outline" 
            className={`transition-all duration-300 ${
              isProcessing 
                ? 'border-yellow-500 text-yellow-500 animate-pulse' 
                : 'border-green-500 text-green-500'
            }`}
          >
            {isProcessing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⏳</span>
                Testing...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <span className="animate-pulse">✓</span>
                Ready
              </span>
            )}
          </Badge>
        </div>
      </div>

      {/* Strategy Performance Metrics */}
      <StrategyMetricsPanel 
        performanceMetrics={backtestHistory[0]?.performance_metrics}
        strategyType="topstep"
      />

      {/* Automated Learning & Testing */}
      <AutomatedTestingPanel />

      {/* Quick Backtest Runner */}
      <Card className="bg-panel border-gray-700 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200 hover:shadow-lg transition-shadow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Play className={`h-5 w-5 ${isProcessing ? 'animate-pulse' : ''}`} />
            Quick Backtest Runner
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Tickers (comma-separated)</label>
              <Input
                type="text"
                value={quickBacktest.tickers}
                onChange={(e) => setQuickBacktest({ ...quickBacktest, tickers: e.target.value })}
                placeholder="AAPL,MSFT,NVDA"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Enter stock ticker symbols separated by commas
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Start Date</label>
                <Input
                  type="date"
                  value={quickBacktest.startDate}
                  onChange={(e) => setQuickBacktest({ ...quickBacktest, startDate: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">End Date</label>
                <Input
                  type="date"
                  value={quickBacktest.endDate}
                  onChange={(e) => setQuickBacktest({ ...quickBacktest, endDate: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Initial Capital</label>
                <Input
                  type="number"
                  value={quickBacktest.initialCapital}
                  onChange={(e) => setQuickBacktest({ ...quickBacktest, initialCapital: e.target.value })}
                  placeholder="100000"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                onClick={handleQuickBacktest} 
                disabled={isProcessing}
                className="flex-1 hover:scale-105 active:scale-95 transition-transform duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className={`h-4 w-4 mr-2 ${isProcessing ? 'animate-spin' : ''}`} />
                {isProcessing ? 'Running...' : 'Run Backtest'}
              </Button>
              <p className="text-xs text-muted-foreground animate-in fade-in duration-500">
                Using all available agents
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Strategy Performance Comparison */}
      <Card className="bg-panel border-gray-700">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BarChart3 className="h-5 w-5" />
            Strategy Performance Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          {strategyComparisons.length > 0 ? (
            <div className="space-y-4">
              {strategyComparisons.map((strategy) => (
                <div key={strategy.flow_id} className="p-4 rounded-lg bg-background/50 border border-border">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-primary">{strategy.flow_name}</h3>
                      <p className="text-xs text-muted-foreground">
                        {strategy.total_tests} tests completed
                      </p>
                    </div>
                    <Badge variant="outline" className={strategy.avg_sharpe > 1.0 ? 'border-green-500 text-green-500' : 'border-yellow-500 text-yellow-500'}>
                      Sharpe: {strategy.avg_sharpe.toFixed(2)}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Avg Return</p>
                      <p className={`text-sm font-semibold ${strategy.avg_return > 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {(strategy.avg_return * 100).toFixed(2)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Max Drawdown</p>
                      <p className="text-sm font-semibold text-red-500">
                        {(strategy.max_drawdown * 100).toFixed(2)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Win Rate</p>
                      <p className="text-sm font-semibold text-primary">
                        {(strategy.win_rate * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Best Sharpe</p>
                      <p className="text-sm font-semibold text-green-500">
                        {strategy.best_result?.performance_metrics?.sharpe_ratio?.toFixed(2) || 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No backtest results yet.</p>
              <p className="text-xs text-muted-foreground mt-1">Run your first backtest to see strategy comparisons.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Breakthroughs & Losses */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Breakthroughs */}
        <Card className="bg-panel border-gray-700">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Lightbulb className="h-5 w-5 text-yellow-500" />
              Breakthroughs
              <Badge variant="outline" className="ml-auto">{breakthroughs.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {breakthroughs.length > 0 ? (
              <div className="space-y-3">
                {breakthroughs.map((result) => (
                  <div key={result.id} className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/50">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-medium text-primary">
                          {result.completed_at ? new Date(result.completed_at).toLocaleDateString() : 'Unknown'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Flow: {result.flow_id}
                        </p>
                      </div>
                      {result.performance_metrics?.sharpe_ratio && (
                        <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/50">
                          Sharpe: {result.performance_metrics.sharpe_ratio.toFixed(2)}
                        </Badge>
                      )}
                    </div>
                    {result.performance_metrics?.total_return && (
                      <p className="text-sm text-green-500 font-semibold">
                        Return: +{(result.performance_metrics.total_return * 100).toFixed(2)}%
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Lightbulb className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
                <p className="text-sm text-muted-foreground">No breakthroughs yet.</p>
                <p className="text-xs text-muted-foreground mt-1">Breakthroughs are results with Sharpe ratio &gt; 1.5</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Losses */}
        <Card className="bg-panel border-gray-700">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <XCircle className="h-5 w-5 text-red-500" />
              Significant Losses
              <Badge variant="outline" className="ml-auto">{losses.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {losses.length > 0 ? (
              <div className="space-y-3">
                {losses.map((result) => (
                  <div key={result.id} className="p-3 rounded-lg bg-red-500/10 border border-red-500/50">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-medium text-primary">
                          {result.completed_at ? new Date(result.completed_at).toLocaleDateString() : 'Unknown'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Flow: {result.flow_id}
                        </p>
                      </div>
                      {result.performance_metrics?.max_drawdown && (
                        <Badge className="bg-red-500/20 text-red-500 border-red-500/50">
                          Drawdown: {(result.performance_metrics.max_drawdown * 100).toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                    {result.performance_metrics?.total_return && (
                      <p className="text-sm text-red-500 font-semibold">
                        Return: {(result.performance_metrics.total_return * 100).toFixed(2)}%
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <XCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
                <p className="text-sm text-muted-foreground">No significant losses yet.</p>
                <p className="text-xs text-muted-foreground mt-1">Losses are results with drawdown &gt; 20%</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Department Performance Overview */}
      <Card className="bg-panel border-gray-700">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Building2 className="h-5 w-5" />
            Department Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          {departmentPerformance.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {departmentPerformance
                .filter(dept => dept.agents.length > 0)
                .map(dept => {
                  const IconComponent = getDepartmentIcon(dept.department.icon);
                  const deptPerf = departmentPerformance.find(d => d.department.id === dept.department.id);
                  return (
                    <div
                      key={dept.department.id}
                      className={`p-4 rounded-lg border ${getDepartmentColorClass(dept.department)} cursor-pointer hover:opacity-80 transition-opacity`}
                      onClick={() => setSelectedDepartment(dept.department)}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <IconComponent className="h-4 w-4" />
                            <h3 className="font-semibold text-primary">{dept.department.name}</h3>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {dept.department.description}
                          </p>
                        </div>
                        <Badge className={getDepartmentColorClass(dept.department)} variant="outline">
                          {dept.agents.length}
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Total Runs</span>
                          <span className="font-medium text-primary">{dept.total_runs}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Avg Performance</span>
                          <span className={`font-semibold ${dept.avg_performance > 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {dept.avg_performance.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Win Rate</span>
                          <span className={`font-semibold ${dept.win_rate > 0.5 ? 'text-green-500' : 'text-red-500'}`}>
                            {(dept.win_rate * 100).toFixed(0)}%
                          </span>
                        </div>
                        {dept.top_performer && (
                          <div className="pt-2 border-t border-border/50">
                            <p className="text-xs text-muted-foreground mb-1">Top Performer</p>
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-primary">
                                {dept.top_performer.agent_name}
                              </span>
                              {dept.top_performer.role && (
                                <Badge className={getRankColor(dept.top_performer.role.rank)} variant="outline">
                                  {dept.top_performer.role.rank}
                                </Badge>
                              )}
                            </div>
                          </div>
                        )}
                        {dept.needs_attention && dept.needs_attention.length > 0 && (
                          <div className="pt-2 border-t border-border/50">
                            <p className="text-xs text-red-500 mb-1">⚠️ {dept.needs_attention.length} need attention</p>
                          </div>
                        )}
                      </div>
                      <div className="mt-3 pt-2 border-t border-border/50">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedDepartment(dept.department);
                          }}
                        >
                          View Analysis →
                        </Button>
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <div className="text-center py-8">
              <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No department data yet.</p>
              <p className="text-xs text-muted-foreground mt-1">Run backtests to see department performance.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Department Detailed Analysis */}
      {selectedDepartment && (() => {
        const deptData = departmentPerformance.find(d => d.department.id === selectedDepartment.id);
        if (!deptData) return null;
        const IconComponent = getDepartmentIcon(selectedDepartment.icon);
        
        return (
          <Card className="bg-panel border-gray-700">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <IconComponent className="h-5 w-5" />
                  {selectedDepartment.name} - Detailed Analysis
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedDepartment(null)}
                >
                  <XCircle className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Department Overview */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-background/50 border border-border">
                    <p className="text-xs text-muted-foreground mb-1">Total Employees</p>
                    <p className="text-2xl font-bold text-primary">{deptData.agents.length}</p>
                  </div>
                  <div className="p-4 rounded-lg bg-background/50 border border-border">
                    <p className="text-xs text-muted-foreground mb-1">Total Runs</p>
                    <p className="text-2xl font-bold text-primary">{deptData.total_runs}</p>
                  </div>
                  <div className="p-4 rounded-lg bg-background/50 border border-border">
                    <p className="text-xs text-muted-foreground mb-1">Avg Performance</p>
                    <p className={`text-2xl font-bold ${deptData.avg_performance > 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {deptData.avg_performance.toFixed(2)}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-background/50 border border-border">
                    <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                    <p className={`text-2xl font-bold ${deptData.win_rate > 0.5 ? 'text-green-500' : 'text-red-500'}`}>
                      {(deptData.win_rate * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                {/* Department Health Score */}
                <div>
                  <h3 className="text-sm font-semibold text-primary mb-3">Department Health Score</h3>
                  <div className="p-4 rounded-lg bg-background/50 border border-border">
                    {(() => {
                      const healthScore = (
                        (deptData.avg_performance > 0 ? 30 : 0) +
                        (deptData.win_rate > 0.5 ? 30 : deptData.win_rate > 0.3 ? 15 : 0) +
                        (deptData.total_runs > 10 ? 20 : deptData.total_runs > 5 ? 10 : 0) +
                        (deptData.agents.length > 2 ? 20 : deptData.agents.length > 0 ? 10 : 0)
                      );
                      const healthLevel = healthScore >= 70 ? 'excellent' : healthScore >= 50 ? 'good' : healthScore >= 30 ? 'fair' : 'poor';
                      const healthColor = healthLevel === 'excellent' ? 'text-green-500' : 
                                         healthLevel === 'good' ? 'text-blue-500' :
                                         healthLevel === 'fair' ? 'text-yellow-500' : 'text-red-500';
                      
                      return (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-primary">Overall Health</span>
                            <span className={`text-2xl font-bold ${healthColor}`}>{healthScore}/100</span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-4">
                            <div 
                              className={`h-2 rounded-full ${
                                healthLevel === 'excellent' ? 'bg-green-500' :
                                healthLevel === 'good' ? 'bg-blue-500' :
                                healthLevel === 'fair' ? 'bg-yellow-500' : 'bg-red-500'
                              }`}
                              style={{ width: `${healthScore}%` }}
                            />
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                            <div>
                              <span className="text-muted-foreground">Performance: </span>
                              <span className={deptData.avg_performance > 0 ? 'text-green-500' : 'text-red-500'}>
                                {deptData.avg_performance > 0 ? '✓ Positive' : '✗ Negative'}
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Win Rate: </span>
                              <span className={deptData.win_rate > 0.5 ? 'text-green-500' : deptData.win_rate > 0.3 ? 'text-yellow-500' : 'text-red-500'}>
                                {(deptData.win_rate * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Activity: </span>
                              <span className={deptData.total_runs > 10 ? 'text-green-500' : deptData.total_runs > 5 ? 'text-yellow-500' : 'text-red-500'}>
                                {deptData.total_runs > 10 ? 'High' : deptData.total_runs > 5 ? 'Medium' : 'Low'}
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Team Size: </span>
                              <span className={deptData.agents.length > 2 ? 'text-green-500' : 'text-yellow-500'}>
                                {deptData.agents.length} {deptData.agents.length === 1 ? 'employee' : 'employees'}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                {/* All Employees in Department */}
                <div>
                  <h3 className="text-sm font-semibold text-primary mb-3">All Employees in {selectedDepartment.name}</h3>
                  <div className="space-y-2">
                    {deptData.agents
                      .sort((a, b) => {
                        // Sort by rank (higher rank first), then by performance
                        const rankOrder = [Rank.PARTNER, Rank.MANAGING_DIRECTOR, Rank.DIRECTOR, Rank.VICE_PRESIDENT, Rank.SENIOR_ANALYST, Rank.ASSOCIATE, Rank.ANALYST, Rank.INTERN];
                        const aRank = a.role ? rankOrder.indexOf(a.role.rank) : 999;
                        const bRank = b.role ? rankOrder.indexOf(b.role.rank) : 999;
                        if (aRank !== bRank) return aRank - bRank;
                        return b.avg_contribution - a.avg_contribution;
                      })
                      .map(agent => (
                        <div
                          key={agent.agent_key}
                          className={`p-4 rounded-lg border ${
                            agent.avg_contribution > 0.5
                              ? 'bg-green-500/10 border-green-500/50'
                              : agent.avg_contribution < 0
                              ? 'bg-red-500/10 border-red-500/50'
                              : 'bg-background/50 border-border'
                          }`}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <p className="font-semibold text-primary">{agent.agent_name}</p>
                                {agent.role && (
                                  <>
                                    <Badge className={getRankColor(agent.role.rank)} variant="outline">
                                      {agent.role.rank}
                                    </Badge>
                                    <Badge variant="outline" className="text-xs">
                                      {agent.role.authority}
                                    </Badge>
                                  </>
                                )}
                              </div>
                              {agent.role && (
                                <p className="text-xs text-muted-foreground mb-2">
                                  {agent.role.specialization}
                                </p>
                              )}
                              {agent.current_ticker && (
                                <p className="text-xs text-primary">
                                  Currently working on: <span className="font-medium">{agent.current_ticker}</span>
                                </p>
                              )}
                            </div>
                            <div className="text-right">
                              <Badge className={agent.avg_contribution > 0 ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'} variant="outline">
                                {agent.avg_contribution.toFixed(2)}
                              </Badge>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-xs text-muted-foreground">Runs</p>
                              <p className="font-medium text-primary">{agent.total_runs}</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Win Rate</p>
                              <p className={`font-medium ${agent.win_rate > 0.5 ? 'text-green-500' : 'text-red-500'}`}>
                                {(agent.win_rate * 100).toFixed(0)}%
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Best</p>
                              <p className="font-medium text-green-500">
                                {agent.best_performance?.toFixed(2) || 'N/A'}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Status</p>
                              <Badge className={getStatusColor(agent.status)} variant="outline">
                                {agent.status}
                              </Badge>
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Recommendations */}
                <div>
                  <h3 className="text-sm font-semibold text-primary mb-3">Recommendations</h3>
                  <div className="space-y-2">
                    {deptData.avg_performance < 0 && (
                      <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/50">
                        <p className="text-sm text-red-500 font-medium">⚠️ Department Performance is Negative</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Consider reviewing strategies or reassigning resources. Average performance: {deptData.avg_performance.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {deptData.win_rate < 0.3 && (
                      <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/50">
                        <p className="text-sm text-yellow-500 font-medium">⚠️ Low Win Rate</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Win rate is below 30%. Consider additional training or strategy adjustments.
                        </p>
                      </div>
                    )}
                    {deptData.total_runs < 5 && (
                      <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                        <p className="text-sm text-blue-500 font-medium">ℹ️ Limited Data</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Only {deptData.total_runs} runs completed. Run more backtests for better insights.
                        </p>
                      </div>
                    )}
                    {deptData.needs_attention && deptData.needs_attention.length > 0 && (
                      <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/50">
                        <p className="text-sm text-orange-500 font-medium">⚠️ {deptData.needs_attention.length} Employee(s) Need Attention</p>
                        <ul className="text-xs text-muted-foreground mt-1 list-disc list-inside">
                          {deptData.needs_attention.map(agent => (
                            <li key={agent.agent_key}>
                              {agent.agent_name}: {agent.avg_contribution.toFixed(2)} avg, {(agent.win_rate * 100).toFixed(0)}% win rate
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {deptData.avg_performance > 0.5 && deptData.win_rate > 0.6 && (
                      <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/50">
                        <p className="text-sm text-green-500 font-medium">✓ Department Performing Well</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Keep current strategies. Consider expanding this department's role.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* Employee Performance Tracking */}
      <Card className="bg-panel border-gray-700">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Users className="h-5 w-5" />
            Employee Performance Tracking
          </CardTitle>
        </CardHeader>
        <CardContent>
          {agentPerformance.length > 0 ? (
            <div className="space-y-4">
              {/* Organizational Summary */}
              <div className="p-4 rounded-lg bg-background/50 border border-border mb-4">
                <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Organizational Structure
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Total Employees</p>
                    <p className="text-lg font-semibold text-primary">{agentPerformance.length}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Active Departments</p>
                    <p className="text-lg font-semibold text-primary">
                      {departmentPerformance.filter(d => d.agents.length > 0).length}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Partners/Executives</p>
                    <p className="text-lg font-semibold text-indigo-500">
                      {agentPerformance.filter(a => a.role?.rank === Rank.PARTNER || a.role?.rank === Rank.MANAGING_DIRECTOR).length}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Directors & VPs</p>
                    <p className="text-lg font-semibold text-yellow-500">
                      {agentPerformance.filter(a => 
                        a.role?.rank === Rank.DIRECTOR || a.role?.rank === Rank.VICE_PRESIDENT
                      ).length}
                    </p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mb-2">Department Breakdown:</p>
                  <div className="flex flex-wrap gap-2">
                    {departmentPerformance
                      .filter(d => d.agents.length > 0)
                      .map(dept => (
                        <Badge 
                          key={dept.department.id} 
                          className={getDepartmentColorClass(dept.department)} 
                          variant="outline"
                        >
                          {dept.department.name}: {dept.agents.length}
                        </Badge>
                      ))}
                  </div>
                </div>
              </div>
              {/* Top Performers */}
              <div>
                <h3 className="text-sm font-semibold text-green-500 mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Top Performers
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {agentPerformance
                    .filter(a => a.avg_contribution > 0.5)
                    .slice(0, 6)
                    .map(agent => (
                      <div key={agent.agent_key} className="p-4 rounded-lg bg-green-500/10 border border-green-500/50">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-semibold text-primary text-sm">{agent.agent_name}</p>
                              {agent.role && (
                                <>
                                  <Badge className={getRankColor(agent.role.rank)} variant="outline">
                                    {agent.role.rank}
                                  </Badge>
                                  <Badge className={getDepartmentColorClass(agent.role.department)} variant="outline">
                                    {agent.role.department.name}
                                  </Badge>
                                </>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {agent.total_runs} runs • {agent.successful_runs} successful
                            </p>
                            {agent.role && (
                              <p className="text-xs text-muted-foreground mt-1">
                                Authority: {agent.role.authority} • {agent.role.specialization}
                              </p>
                            )}
                          </div>
                          <Badge className="bg-green-500/20 text-green-500 border-green-500/50">
                            {agent.avg_contribution.toFixed(2)}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-3">
                          <div>
                            <p className="text-xs text-muted-foreground">Win Rate</p>
                            <p className="text-sm font-semibold text-green-500">
                              {(agent.win_rate * 100).toFixed(0)}%
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Best</p>
                            <p className="text-sm font-semibold text-primary">
                              {agent.best_performance?.toFixed(2) || 'N/A'}
                            </p>
                          </div>
                        </div>
                        {agent.performance_trend !== 'unknown' && (
                          <div className="mt-2 flex items-center gap-1">
                            {agent.performance_trend === 'improving' && (
                              <>
                                <TrendingUp className="h-3 w-3 text-green-500" />
                                <span className="text-xs text-green-500">Improving</span>
                              </>
                            )}
                            {agent.performance_trend === 'declining' && (
                              <>
                                <TrendingDown className="h-3 w-3 text-red-500" />
                                <span className="text-xs text-red-500">Declining</span>
                              </>
                            )}
                            {agent.performance_trend === 'stable' && (
                              <>
                                <Activity className="h-3 w-3 text-yellow-500" />
                                <span className="text-xs text-yellow-500">Stable</span>
                              </>
                            )}
                          </div>
                        )}
                        {agent.status !== 'IDLE' && (
                          <div className="mt-2 pt-2 border-t border-border">
                            <p className="text-xs text-muted-foreground">
                              Status: <span className="text-primary font-medium">{agent.status}</span>
                              {agent.current_ticker && (
                                <> • Working on: <span className="text-primary font-medium">{agent.current_ticker}</span></>
                              )}
                            </p>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* Underperformers */}
              <div>
                <h3 className="text-sm font-semibold text-red-500 mb-3 flex items-center gap-2">
                  <TrendingDown className="h-4 w-4" />
                  Needs Improvement
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {agentPerformance
                    .filter(a => a.avg_contribution < 0 || a.failed_runs > a.successful_runs)
                    .slice(0, 6)
                    .map(agent => (
                      <div key={agent.agent_key} className="p-4 rounded-lg bg-red-500/10 border border-red-500/50">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-semibold text-primary text-sm">{agent.agent_name}</p>
                              {agent.role && (
                                <>
                                  <Badge className={getRankColor(agent.role.rank)} variant="outline">
                                    {agent.role.rank}
                                  </Badge>
                                  <Badge className={getDepartmentColorClass(agent.role.department)} variant="outline">
                                    {agent.role.department.name}
                                  </Badge>
                                </>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {agent.total_runs} runs • {agent.failed_runs} failed
                            </p>
                            {agent.role && (
                              <p className="text-xs text-muted-foreground mt-1">
                                Authority: {agent.role.authority} • {agent.role.specialization}
                              </p>
                            )}
                          </div>
                          <Badge className="bg-red-500/20 text-red-500 border-red-500/50">
                            {agent.avg_contribution.toFixed(2)}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-3">
                          <div>
                            <p className="text-xs text-muted-foreground">Win Rate</p>
                            <p className="text-sm font-semibold text-red-500">
                              {(agent.win_rate * 100).toFixed(0)}%
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Worst</p>
                            <p className="text-sm font-semibold text-red-500">
                              {agent.worst_performance?.toFixed(2) || 'N/A'}
                            </p>
                          </div>
                        </div>
                        {agent.performance_trend === 'declining' && (
                          <div className="mt-2 flex items-center gap-1">
                            <AlertCircle className="h-3 w-3 text-red-500" />
                            <span className="text-xs text-red-500">Performance declining</span>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* All Employees Table */}
              <div>
                <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  All Employees Overview
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-2 text-muted-foreground">Employee</th>
                        <th className="text-left p-2 text-muted-foreground">Department</th>
                        <th className="text-left p-2 text-muted-foreground">Rank</th>
                        <th className="text-left p-2 text-muted-foreground">Authority</th>
                        <th className="text-right p-2 text-muted-foreground">Runs</th>
                        <th className="text-right p-2 text-muted-foreground">Win Rate</th>
                        <th className="text-right p-2 text-muted-foreground">Avg Performance</th>
                        <th className="text-right p-2 text-muted-foreground">Best</th>
                        <th className="text-right p-2 text-muted-foreground">Worst</th>
                        <th className="text-center p-2 text-muted-foreground">Status</th>
                        <th className="text-center p-2 text-muted-foreground">Trend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agentPerformance.map(agent => (
                        <tr key={agent.agent_key} className="border-b border-border/50 hover:bg-background/50">
                          <td className="p-2">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <p className="font-medium text-primary">{agent.agent_name}</p>
                                {agent.role && (
                                  <>
                                    <Badge className={getRankColor(agent.role.rank)} variant="outline">
                                      {agent.role.rank}
                                    </Badge>
                                    <Badge className={getDepartmentColorClass(agent.role.department)} variant="outline">
                                      {agent.role.department.name}
                                    </Badge>
                                  </>
                                )}
                              </div>
                              {agent.role && (
                                <p className="text-xs text-muted-foreground mb-1">
                                  {agent.role.authority} • {agent.role.specialization}
                                </p>
                              )}
                              {agent.current_ticker && (
                                <p className="text-xs text-muted-foreground">Working on: {agent.current_ticker}</p>
                              )}
                            </div>
                          </td>
                          <td className="text-left p-2">
                            {agent.role ? (
                              <Badge className={getDepartmentColorClass(agent.role.department)} variant="outline">
                                {agent.role.department.name}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </td>
                          <td className="text-left p-2">
                            {agent.role ? (
                              <Badge className={getRankColor(agent.role.rank)} variant="outline">
                                {agent.role.rank}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </td>
                          <td className="text-left p-2">
                            {agent.role ? (
                              <span className="text-xs text-muted-foreground">{agent.role.authority}</span>
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </td>
                          <td className="text-right p-2">
                            <span className="text-primary">{agent.total_runs}</span>
                            <span className="text-xs text-muted-foreground ml-1">
                              ({agent.successful_runs}✓ / {agent.failed_runs}✗)
                            </span>
                          </td>
                          <td className="text-right p-2">
                            <span className={agent.win_rate > 0.5 ? 'text-green-500' : 'text-red-500'}>
                              {(agent.win_rate * 100).toFixed(0)}%
                            </span>
                          </td>
                          <td className="text-right p-2">
                            <span className={agent.avg_contribution > 0 ? 'text-green-500' : 'text-red-500'}>
                              {agent.avg_contribution.toFixed(2)}
                            </span>
                          </td>
                          <td className="text-right p-2">
                            <span className="text-green-500">
                              {agent.best_performance?.toFixed(2) || 'N/A'}
                            </span>
                          </td>
                          <td className="text-right p-2">
                            <span className="text-red-500">
                              {agent.worst_performance?.toFixed(2) || 'N/A'}
                            </span>
                          </td>
                          <td className="text-center p-2">
                            <Badge className={getStatusColor(agent.status)} variant="outline">
                              {agent.status}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            {agent.performance_trend === 'improving' && (
                              <TrendingUp className="h-4 w-4 text-green-500 mx-auto" />
                            )}
                            {agent.performance_trend === 'declining' && (
                              <TrendingDown className="h-4 w-4 text-red-500 mx-auto" />
                            )}
                            {agent.performance_trend === 'stable' && (
                              <Activity className="h-4 w-4 text-yellow-500 mx-auto" />
                            )}
                            {agent.performance_trend === 'unknown' && (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <Users className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No agent performance data yet.</p>
              <p className="text-xs text-muted-foreground mt-1">Run backtests to start tracking employee performance.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Backtest History */}
      <Card className="bg-panel border-gray-700">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BookOpen className="h-5 w-5" />
            Backtest History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {backtestHistory.length > 0 ? (
            <div className="space-y-3">
              {backtestHistory.slice(0, 20).map((result) => (
                <div key={result.id} className="p-4 rounded-lg bg-background/50 border border-border">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-sm font-medium text-primary">
                        {result.completed_at ? new Date(result.completed_at).toLocaleString() : 'Unknown'}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Flow ID: {result.flow_id}
                      </p>
                    </div>
                    <Badge className={getStatusColor(result.status)} variant="outline">
                      {result.status}
                    </Badge>
                  </div>
                  {result.performance_metrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {result.performance_metrics.sharpe_ratio !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">Sharpe Ratio</p>
                          <p className="text-sm font-semibold text-primary">
                            {result.performance_metrics.sharpe_ratio.toFixed(2)}
                          </p>
                        </div>
                      )}
                      {result.performance_metrics.total_return !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">Total Return</p>
                          <p className={`text-sm font-semibold ${result.performance_metrics.total_return > 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {(result.performance_metrics.total_return * 100).toFixed(2)}%
                          </p>
                        </div>
                      )}
                      {result.performance_metrics.max_drawdown !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">Max Drawdown</p>
                          <p className="text-sm font-semibold text-red-500">
                            {(result.performance_metrics.max_drawdown * 100).toFixed(2)}%
                          </p>
                        </div>
                      )}
                      {result.performance_metrics.win_rate !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">Win Rate</p>
                          <p className="text-sm font-semibold text-primary">
                            {(result.performance_metrics.win_rate * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No backtest history yet.</p>
              <p className="text-xs text-muted-foreground mt-1">Run backtests to build your history.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
