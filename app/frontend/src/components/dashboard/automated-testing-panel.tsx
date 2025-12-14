import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useNodeContext } from '@/contexts/node-context';
import { 
  Play, Square, Pause, TrendingUp, TrendingDown, Target, Zap, 
  CheckCircle2, XCircle, Clock, BarChart3, Brain, Settings, AlertCircle
} from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';
// Flow type kept for optional compatibility but not required
type Flow = any;
import { BacktestRequest } from '@/services/types';
import { api } from '@/services/api';

interface AutomatedTestingPanelProps {
  flows?: Flow[]; // Optional, not required
}

interface TestRun {
  id: string;
  run_name: string;
  start_date: string;
  end_date: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  result?: {
    sharpe_ratio?: number;
    total_return?: number;
    max_drawdown?: number;
    win_rate?: number;
  };
  completed_at?: string;
}

interface ProfitabilityTarget {
  sharpe_ratio: number;
  min_runs: number;
  consecutive_wins: number;
  max_drawdown: number;
}

export function AutomatedTestingPanel({ flows = [] }: AutomatedTestingPanelProps) {
  const nodeContext = useNodeContext();
  const [isProcessing, setIsProcessing] = useState(false);
  
  const [isAutoTesting, setIsAutoTesting] = useState(false);
  const [testQueue, setTestQueue] = useState<TestRun[]>([]);
  const [completedTests, setCompletedTests] = useState<TestRun[]>([]);
  const [isProfitable, setIsProfitable] = useState(false);
  const [learningProgress, setLearningProgress] = useState(0);
  
  // Track intervals and timeouts for cleanup
  const intervalRefs = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const timeoutRefs = useRef<Map<string, NodeJS.Timeout>>(new Map());
  
  // Configuration
  const [config, setConfig] = useState({
    dateRangeDays: 90,
    testInterval: 30, // seconds between tests
    maxConcurrentTests: 1,
    autoAdjust: true,
  });

  // Profitability criteria
  const [targets, setTargets] = useState<ProfitabilityTarget>({
    sharpe_ratio: 1.5,
    min_runs: 10,
    consecutive_wins: 3,
    max_drawdown: 0.15,
  });

  // Test statistics
  const [stats, setStats] = useState({
    totalTests: 0,
    successfulTests: 0,
    failedTests: 0,
    avgSharpe: 0,
    avgReturn: 0,
    bestSharpe: 0,
    worstSharpe: 0,
    consecutiveWins: 0,
    consecutiveLosses: 0,
  });

  useEffect(() => {
    if (isAutoTesting && !isProcessing && testQueue.length === 0) {
      // Check if we've proven profitability
      checkProfitability();
      
      // If not profitable, queue next test
      if (!isProfitable) {
        queueNextTest();
      }
    }
  }, [isAutoTesting, isProcessing, testQueue.length, isProfitable]);

  const checkProfitability = () => {
    if (completedTests.length < targets.min_runs) {
      setIsProfitable(false);
      setLearningProgress((completedTests.length / targets.min_runs) * 50);
      return;
    }

    const recentTests = completedTests.slice(-targets.consecutive_wins);
    const allProfitable = recentTests.every(test => 
      test.result?.sharpe_ratio && 
      test.result.sharpe_ratio >= targets.sharpe_ratio &&
      test.result.max_drawdown && 
      test.result.max_drawdown <= targets.max_drawdown
    );

    const avgSharpe = completedTests
      .map(t => t.result?.sharpe_ratio || 0)
      .reduce((a, b) => a + b, 0) / completedTests.length;

    if (allProfitable && avgSharpe >= targets.sharpe_ratio) {
      setIsProfitable(true);
      setLearningProgress(100);
    } else {
      setIsProfitable(false);
      const progress = Math.min(
        50 + (completedTests.length / targets.min_runs) * 30 + 
        (recentTests.filter(t => t.result?.sharpe_ratio && t.result.sharpe_ratio >= targets.sharpe_ratio).length / targets.consecutive_wins) * 20,
        99
      );
      setLearningProgress(progress);
    }
  };

  // Create default graph structure for dashboard runs
  const createDefaultGraph = useCallback(async () => {
    const nodes: any[] = [];
    const edges: any[] = [];
    
    try {
      // Get all agents from the API
      const agentsList = await api.getAgents();
      
      agentsList.forEach((agent, index) => {
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
        
        // Connect agents in a simple chain
        if (index > 0) {
          const prevNodeId = nodes[nodes.length - 2].id;
          edges.push({
            id: `edge_${prevNodeId}_${nodeId}`,
            source: prevNodeId,
            target: nodeId,
          });
        }
      });
    } catch (error) {
      console.error('Failed to fetch agents for default graph:', error);
      // Fallback to basic structure
      const defaultAgents = [
        'fundamental_analyst',
        'technical_analyst',
        'sentiment_analyst',
        'portfolio_manager',
      ];
      
      defaultAgents.forEach((agentKey, index) => {
        const nodeId = `${agentKey}_${Date.now()}_${index}`;
        nodes.push({
          id: nodeId,
          type: 'agent-node',
          data: { name: agentKey },
          position: { x: 100 + index * 200, y: 100 },
        });
        
        if (index > 0) {
          edges.push({
            id: `edge_${nodes[nodes.length - 2].id}_${nodeId}`,
            source: nodes[nodes.length - 2].id,
            target: nodeId,
          });
        }
      });
    }
    
    return { nodes, edges };
  }, []);

  const queueNextTest = async () => {
    // No flow required - always proceed

    // Generate date range (rolling window)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - config.dateRangeDays);

    // Adjust date range based on learning (if enabled)
    let adjustedDays = config.dateRangeDays;
    if (config.autoAdjust && completedTests.length > 0) {
      const recentAvgReturn = completedTests
        .slice(-5)
        .map(t => t.result?.total_return || 0)
        .reduce((a, b) => a + b, 0) / Math.min(5, completedTests.length);
      
      // If recent performance is poor, test shorter periods
      if (recentAvgReturn < -0.1) {
        adjustedDays = Math.max(30, config.dateRangeDays - 15);
      }
      // If recent performance is good, test longer periods
      else if (recentAvgReturn > 0.1) {
        adjustedDays = Math.min(180, config.dateRangeDays + 15);
      }
    }

    const testRun: TestRun = {
      id: `test-${Date.now()}`,
      run_name: `Test Run ${new Date().toLocaleString()}`,
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0],
      status: 'queued',
    };

    setTestQueue(prev => [...prev, testRun]);
    
    // Wait for interval before running
    setTimeout(() => {
      runTest(testRun);
    }, config.testInterval * 1000);
  };


  const runTest = async (testRun: TestRun) => {
    // Use a simple session ID for tracking
    const sessionId = `dashboard-${Date.now()}`;
    setIsProcessing(true);

    // Update status to running
    setTestQueue(prev => prev.map(t => 
      t.id === testRun.id ? { ...t, status: 'running' } : t
    ));

    try {
      // Always use default graph with all agents
      const defaultGraph = await createDefaultGraph();
      const graphNodes = defaultGraph.nodes;
      const graphEdges = defaultGraph.edges;
      
      // Default tickers
      const tickers = ['AAPL', 'MSFT', 'NVDA'];
      
      const backtestRequest: BacktestRequest = {
        tickers: tickers,
        graph_nodes: graphNodes,
        graph_edges: graphEdges,
        agent_models: graphNodes.map(node => ({
          agent_id: node.id,
          model_name: undefined,
          model_provider: undefined,
        })),
        start_date: testRun.start_date,
        end_date: testRun.end_date,
        initial_capital: 100000,
      };

      // Run backtest using the backtest API directly
      const { backtestApi } = await import('@/services/backtest-api');
      backtestApi.runBacktest(backtestRequest, nodeContext, sessionId);

      // Monitor for completion by watching node context output data
      const checkInterval = setInterval(() => {
        const outputData = nodeContext.getOutputNodeDataForFlow(sessionId);
        const agentData = nodeContext.getAgentNodeDataForFlow(sessionId);
        
        // Check if backtest is complete
        const backtestAgent = agentData?.['backtest'];
        if (backtestAgent?.status === 'COMPLETE' && outputData?.performance_metrics) {
          // Clean up interval and timeout
          const interval = intervalRefs.current.get(testRun.id);
          if (interval) {
            clearInterval(interval);
            intervalRefs.current.delete(testRun.id);
          }
          const timeout = timeoutRefs.current.get(testRun.id);
          if (timeout) {
            clearTimeout(timeout);
            timeoutRefs.current.delete(testRun.id);
          }
          
          setIsProcessing(false);
          
          // Extract results from output data
          const completedTest: TestRun = {
            ...testRun,
            status: 'completed',
            result: {
              sharpe_ratio: outputData.performance_metrics.sharpe_ratio,
              total_return: outputData.performance_metrics.total_return,
              max_drawdown: outputData.performance_metrics.max_drawdown,
              win_rate: outputData.performance_metrics.win_rate,
            },
            completed_at: new Date().toISOString(),
          };

          // Remove from queue, add to completed
          setTestQueue(prev => prev.filter(t => t.id !== testRun.id));
          setCompletedTests(prev => [completedTest, ...prev].slice(0, 50)); // Keep last 50

          // Update statistics
          updateStats(completedTest);
          
          // Check profitability
          checkProfitability();
        } else if (backtestAgent?.status === 'ERROR') {
          // Clean up interval and timeout
          const interval = intervalRefs.current.get(testRun.id);
          if (interval) {
            clearInterval(interval);
            intervalRefs.current.delete(testRun.id);
          }
          const timeout = timeoutRefs.current.get(testRun.id);
          if (timeout) {
            clearTimeout(timeout);
            timeoutRefs.current.delete(testRun.id);
          }
          setIsProcessing(false);
          setTestQueue(prev => prev.map(t => 
            t.id === testRun.id ? { ...t, status: 'failed' } : t
          ));
        }
      }, 1000); // Check every second
      
      // Store interval for cleanup
      intervalRefs.current.set(testRun.id, checkInterval);

      // Timeout after 5 minutes
      const timeoutId = setTimeout(() => {
        const interval = intervalRefs.current.get(testRun.id);
        if (interval) {
          clearInterval(interval);
          intervalRefs.current.delete(testRun.id);
        }
        timeoutRefs.current.delete(testRun.id);
        setIsProcessing(false);
        const outputData = nodeContext.getOutputNodeDataForFlow(sessionId);
        if (!outputData?.performance_metrics) {
          setTestQueue(prev => prev.map(t => 
            t.id === testRun.id ? { ...t, status: 'failed' } : t
          ));
        }
      }, 5 * 60 * 1000);
      
      // Store timeout for cleanup
      timeoutRefs.current.set(testRun.id, timeoutId);

    } catch (error) {
      console.error('Test failed:', error);
      setIsProcessing(false);
      setTestQueue(prev => prev.map(t => 
        t.id === testRun.id ? { ...t, status: 'failed' } : t
      ));
    }
  };


  const updateStats = (test: TestRun) => {
    // Update completed tests first, then calculate stats
    setCompletedTests(prevCompleted => {
      const newCompleted = [...prevCompleted, test];
      
      // Calculate stats from the new completed list
      const sharpeRatios = newCompleted
        .map(t => t.result?.sharpe_ratio || 0)
        .filter(s => s !== 0);
      const returns = newCompleted
        .map(t => t.result?.total_return || 0)
        .filter(r => r !== 0);

      const successful = newCompleted.filter(t => 
        t.result?.sharpe_ratio && t.result.sharpe_ratio >= targets.sharpe_ratio
      ).length;

      const failed = newCompleted.filter(t => 
        t.result?.sharpe_ratio && t.result.sharpe_ratio < targets.sharpe_ratio
      ).length;

      // Calculate consecutive wins/losses
      let consecutiveWins = 0;
      let consecutiveLosses = 0;
      for (let i = 0; i < newCompleted.length; i++) {
        const testItem = newCompleted[i];
        if (testItem.result?.sharpe_ratio && testItem.result.sharpe_ratio >= targets.sharpe_ratio) {
          consecutiveWins++;
          consecutiveLosses = 0;
        } else if (testItem.result?.sharpe_ratio !== undefined) {
          consecutiveLosses++;
          consecutiveWins = 0;
        }
      }

      // Update stats
      setStats({
        totalTests: newCompleted.length,
        successfulTests: successful,
        failedTests: failed,
        avgSharpe: sharpeRatios.length > 0 
          ? sharpeRatios.reduce((a, b) => a + b, 0) / sharpeRatios.length 
          : 0,
        avgReturn: returns.length > 0
          ? returns.reduce((a, b) => a + b, 0) / returns.length
          : 0,
        bestSharpe: sharpeRatios.length > 0 ? Math.max(...sharpeRatios) : 0,
        worstSharpe: sharpeRatios.length > 0 ? Math.min(...sharpeRatios) : 0,
        consecutiveWins,
        consecutiveLosses,
      });

      return newCompleted;
    });
  };

  const startAutoTesting = () => {
    setIsAutoTesting(true);
    setIsProfitable(false);
    queueNextTest();
  };

  const stopAutoTesting = () => {
    setIsAutoTesting(false);
    
    // Clean up all intervals
    intervalRefs.current.forEach((interval) => {
      clearInterval(interval);
    });
    intervalRefs.current.clear();
    
    // Clean up all timeouts
    timeoutRefs.current.forEach((timeout) => {
      clearTimeout(timeout);
    });
    timeoutRefs.current.clear();
    
    setTestQueue([]);
  };

  const resetTesting = () => {
    stopAutoTesting();
    setCompletedTests([]);
    setStats({
      totalTests: 0,
      successfulTests: 0,
      failedTests: 0,
      avgSharpe: 0,
      avgReturn: 0,
      bestSharpe: 0,
      worstSharpe: 0,
      consecutiveWins: 0,
      consecutiveLosses: 0,
    });
    setIsProfitable(false);
    setLearningProgress(0);
  };
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      intervalRefs.current.forEach((interval) => {
        clearInterval(interval);
      });
      intervalRefs.current.clear();
      timeoutRefs.current.forEach((timeout) => {
        clearTimeout(timeout);
      });
      timeoutRefs.current.clear();
    };
  }, []);

  return (
    <Card className="bg-panel border-gray-700 animate-in fade-in slide-in-from-bottom-4 duration-500 hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Zap className={`h-5 w-5 ${isAutoTesting ? 'animate-spin' : 'animate-pulse'}`} />
            Automated Learning & Testing
          </CardTitle>
          <div className="flex items-center gap-2">
            {isProfitable && (
              <Badge className="bg-green-500/20 text-green-500 border-green-500/50">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Profitable!
              </Badge>
            )}
            {isAutoTesting ? (
              <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/50">
                <Clock className="h-3 w-3 mr-1" />
                Testing...
              </Badge>
            ) : (
              <Badge variant="outline">Idle</Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Profitability Status */}
          <div className="p-4 rounded-lg bg-background/50 border border-border">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-primary">Learning Progress</h3>
              <span className="text-sm font-bold text-primary">{learningProgress.toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-3 mb-3 overflow-hidden relative">
              <div 
                className={`h-3 rounded-full transition-all duration-1000 ease-out relative ${
                  isProfitable ? 'bg-green-500 animate-pulse' : 
                  learningProgress > 70 ? 'bg-blue-500' :
                  learningProgress > 40 ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, learningProgress))}%` }}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-muted-foreground">Tests: </span>
                <span className="font-medium text-primary">{stats.totalTests}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Success: </span>
                <span className="font-medium text-green-500">{stats.successfulTests}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Avg Sharpe: </span>
                <span className={`font-medium ${stats.avgSharpe >= targets.sharpe_ratio ? 'text-green-500' : 'text-red-500'}`}>
                  {stats.avgSharpe.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Consecutive Wins: </span>
                <span className={`font-medium ${stats.consecutiveWins >= targets.consecutive_wins ? 'text-green-500' : 'text-yellow-500'}`}>
                  {stats.consecutiveWins}/{targets.consecutive_wins}
                </span>
              </div>
            </div>
          </div>

          {/* Profitability Criteria */}
          {!isProfitable && (
            <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/50">
              <div className="flex items-start gap-2 mb-2">
                <Target className="h-4 w-4 text-yellow-500 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-yellow-500 mb-2">Profitability Requirements</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">Min Sharpe: </span>
                      <span className={stats.avgSharpe >= targets.sharpe_ratio ? 'text-green-500' : 'text-yellow-500'}>
                        {stats.avgSharpe.toFixed(2)} / {targets.sharpe_ratio}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Min Runs: </span>
                      <span className={stats.totalTests >= targets.min_runs ? 'text-green-500' : 'text-yellow-500'}>
                        {stats.totalTests} / {targets.min_runs}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Consecutive Wins: </span>
                      <span className={stats.consecutiveWins >= targets.consecutive_wins ? 'text-green-500' : 'text-yellow-500'}>
                        {stats.consecutiveWins} / {targets.consecutive_wins}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Max Drawdown: </span>
                      <span className="text-yellow-500">
                        ≤ {targets.max_drawdown * 100}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Control Buttons */}
          <div className="flex items-center gap-2">
            {!isAutoTesting ? (
              <Button 
                onClick={startAutoTesting} 
                disabled={isProfitable}
                className="flex-1"
              >
                <Play className="h-4 w-4 mr-2" />
                Start Automated Testing
              </Button>
            ) : (
              <Button 
                onClick={stopAutoTesting} 
                variant="destructive"
                className="flex-1"
              >
                <Square className="h-4 w-4 mr-2" />
                Stop Testing
              </Button>
            )}
            <Button 
              onClick={resetTesting} 
              variant="outline"
              disabled={isAutoTesting}
            >
              Reset
            </Button>
          </div>

          {/* Configuration */}
          <div className="p-4 rounded-lg bg-background/50 border border-border">
            <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Configuration
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Date Range (days)</label>
                <Input
                  type="number"
                  value={config.dateRangeDays}
                  onChange={(e) => setConfig({ ...config, dateRangeDays: parseInt(e.target.value) || 90 })}
                  disabled={isAutoTesting}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Test Interval (sec)</label>
                <Input
                  type="number"
                  value={config.testInterval}
                  onChange={(e) => setConfig({ ...config, testInterval: parseInt(e.target.value) || 30 })}
                  disabled={isAutoTesting}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Min Sharpe Ratio</label>
                <Input
                  type="number"
                  step="0.1"
                  value={targets.sharpe_ratio}
                  onChange={(e) => setTargets({ ...targets, sharpe_ratio: parseFloat(e.target.value) || 1.5 })}
                  disabled={isAutoTesting}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Min Runs</label>
                <Input
                  type="number"
                  value={targets.min_runs}
                  onChange={(e) => setTargets({ ...targets, min_runs: parseInt(e.target.value) || 10 })}
                  disabled={isAutoTesting}
                />
              </div>
            </div>
          </div>

          {/* Recent Test Results */}
          {completedTests.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-primary mb-3">Recent Test Results</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {completedTests.slice(0, 10).map(test => (
                  <div
                    key={test.id}
                    className={`p-3 rounded-lg border hover:scale-[1.02] transition-all duration-200 animate-in fade-in slide-in-from-bottom-2 ${
                      test.result?.sharpe_ratio && test.result.sharpe_ratio >= targets.sharpe_ratio
                        ? 'bg-green-500/10 border-green-500/50'
                        : 'bg-red-500/10 border-red-500/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-primary">
                          {test.run_name} • {test.start_date} to {test.end_date}
                        </p>
                        {test.completed_at && (
                          <p className="text-xs text-muted-foreground">
                            {new Date(test.completed_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        {test.result?.sharpe_ratio !== undefined && (
                          <Badge 
                            className={
                              test.result.sharpe_ratio >= targets.sharpe_ratio
                                ? 'bg-green-500/20 text-green-500'
                                : 'bg-red-500/20 text-red-500'
                            }
                            variant="outline"
                          >
                            Sharpe: {test.result.sharpe_ratio.toFixed(2)}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {test.result && (
                      <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
                        <div>
                          <span className="text-muted-foreground">Return: </span>
                          <span className={test.result.total_return && test.result.total_return > 0 ? 'text-green-500' : 'text-red-500'}>
                            {test.result.total_return ? (test.result.total_return * 100).toFixed(2) + '%' : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Drawdown: </span>
                          <span className="text-red-500">
                            {test.result.max_drawdown ? (test.result.max_drawdown * 100).toFixed(2) + '%' : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Win Rate: </span>
                          <span className="text-primary">
                            {test.result.win_rate ? (test.result.win_rate * 100).toFixed(0) + '%' : 'N/A'}
                          </span>
                        </div>
                        <div>
                          {test.result.sharpe_ratio && test.result.sharpe_ratio >= targets.sharpe_ratio ? (
                            <span className="text-green-500 flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Pass
                            </span>
                          ) : (
                            <span className="text-red-500 flex items-center gap-1">
                              <XCircle className="h-3 w-3" />
                              Fail
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Queue Status */}
          {testQueue.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-primary mb-3">Test Queue</h3>
              <div className="space-y-2">
                {testQueue.map(test => (
                  <div
                    key={test.id}
                    className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/50"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-primary">{test.run_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {test.start_date} to {test.end_date}
                        </p>
                      </div>
                      <Badge className="bg-yellow-500/20 text-yellow-500" variant="outline">
                        {test.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </CardContent>
    </Card>
  );
}
