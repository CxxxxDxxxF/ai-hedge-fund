import { API_BASE_URL } from '@/config/api';
import { BacktestRequest } from './types';
import { Flow } from '@/types/flow';

export interface ProfitabilityCriteria {
  min_sharpe_ratio: number;
  min_win_rate: number;
  min_total_return: number;
  min_tests_passed: number; // Number of consecutive successful tests
  max_drawdown_threshold: number;
}

export interface AutomatedTestConfig {
  flow_id: number;
  test_interval_minutes: number;
  max_tests: number;
  date_ranges: Array<{ start_date: string; end_date: string }>;
  profitability_criteria: ProfitabilityCriteria;
  auto_adjust: boolean; // Whether to automatically adjust strategies
  stop_on_profitability: boolean; // Stop when profitable
}

export interface AutomatedTestStatus {
  id: string;
  config: AutomatedTestConfig;
  status: 'running' | 'paused' | 'stopped' | 'completed' | 'profitable';
  current_test: number;
  total_tests: number;
  tests_passed: number;
  tests_failed: number;
  best_result?: {
    sharpe_ratio: number;
    total_return: number;
    date: string;
  };
  last_test_date?: string;
  next_test_date?: string;
  learning_insights?: string[];
  adjustments_made?: number;
}

const DEFAULT_CRITERIA: ProfitabilityCriteria = {
  min_sharpe_ratio: 1.5,
  min_win_rate: 0.6,
  min_total_return: 0.15, // 15% return
  min_tests_passed: 3, // 3 consecutive successful tests
  max_drawdown_threshold: 0.15, // 15% max drawdown
};

class AutomatedTestingService {
  private activeTests = new Map<string, AutomatedTestStatus>();
  private testQueue: Array<{ config: AutomatedTestConfig; priority: number }> = [];

  /**
   * Start automated testing for a flow
   */
  async startAutomatedTesting(
    flow: Flow,
    config: Partial<AutomatedTestConfig> = {}
  ): Promise<AutomatedTestStatus> {
    const testId = `auto-test-${flow.id}-${Date.now()}`;
    
    // Generate date ranges (last 3 months, 6 months, 1 year, etc.)
    const dateRanges = this.generateDateRanges();
    
    const fullConfig: AutomatedTestConfig = {
      flow_id: flow.id,
      test_interval_minutes: config.test_interval_minutes || 60, // Default: test every hour
      max_tests: config.max_tests || 100,
      date_ranges: config.date_ranges || dateRanges,
      profitability_criteria: config.profitability_criteria || DEFAULT_CRITERIA,
      auto_adjust: config.auto_adjust !== false,
      stop_on_profitability: config.stop_on_profitability !== false,
    };

    const testStatus: AutomatedTestStatus = {
      id: testId,
      config: fullConfig,
      status: 'running',
      current_test: 0,
      total_tests: 0,
      tests_passed: 0,
      tests_failed: 0,
      learning_insights: [],
      adjustments_made: 0,
    };

    this.activeTests.set(testId, testStatus);
    
    // Start the testing loop
    this.runTestLoop(testId);
    
    return testStatus;
  }

  /**
   * Generate date ranges for testing
   */
  private generateDateRanges(): Array<{ start_date: string; end_date: string }> {
    const ranges: Array<{ start_date: string; end_date: string }> = [];
    const today = new Date();
    
    // Last 3 months
    const threeMonthsAgo = new Date(today);
    threeMonthsAgo.setMonth(today.getMonth() - 3);
    ranges.push({
      start_date: threeMonthsAgo.toISOString().split('T')[0],
      end_date: today.toISOString().split('T')[0],
    });

    // Last 6 months
    const sixMonthsAgo = new Date(today);
    sixMonthsAgo.setMonth(today.getMonth() - 6);
    ranges.push({
      start_date: sixMonthsAgo.toISOString().split('T')[0],
      end_date: today.toISOString().split('T')[0],
    });

    // Last year
    const oneYearAgo = new Date(today);
    oneYearAgo.setFullYear(today.getFullYear() - 1);
    ranges.push({
      start_date: oneYearAgo.toISOString().split('T')[0],
      end_date: today.toISOString().split('T')[0],
    });

    // Last 2 years
    const twoYearsAgo = new Date(today);
    twoYearsAgo.setFullYear(today.getFullYear() - 2);
    ranges.push({
      start_date: twoYearsAgo.toISOString().split('T')[0],
      end_date: today.toISOString().split('T')[0],
    });

    return ranges;
  }

  /**
   * Main testing loop
   */
  private async runTestLoop(testId: string) {
    const testStatus = this.activeTests.get(testId);
    if (!testStatus || testStatus.status !== 'running') {
      return;
    }

    // Check if we've reached max tests
    if (testStatus.total_tests >= testStatus.config.max_tests) {
      testStatus.status = 'completed';
      return;
    }

    // Check if we've proven profitability
    if (testStatus.config.stop_on_profitability && 
        this.isProfitable(testStatus)) {
      testStatus.status = 'profitable';
      return;
    }

    // Run next test
    try {
      testStatus.current_test++;
      testStatus.total_tests++;
      
      // Get the next date range (cycle through them)
      const dateRangeIndex = (testStatus.total_tests - 1) % testStatus.config.date_ranges.length;
      const dateRange = testStatus.config.date_ranges[dateRangeIndex];
      
      // Run backtest (this would call the actual API)
      const result = await this.runBacktest(testStatus.config.flow_id, dateRange);
      
      // Evaluate result
      const passed = this.evaluateResult(result, testStatus.config.profitability_criteria);
      
      if (passed) {
        testStatus.tests_passed++;
        
        // Update best result
        if (!testStatus.best_result || 
            (result.sharpe_ratio || 0) > testStatus.best_result.sharpe_ratio) {
          testStatus.best_result = {
            sharpe_ratio: result.sharpe_ratio || 0,
            total_return: result.total_return || 0,
            date: new Date().toISOString(),
          };
        }

        // Generate learning insights
        this.generateInsights(testStatus, result, true);
      } else {
        testStatus.tests_failed++;
        this.generateInsights(testStatus, result, false);
      }

      testStatus.last_test_date = new Date().toISOString();
      
      // Auto-adjust if enabled
      if (testStatus.config.auto_adjust && !passed) {
        await this.autoAdjustStrategy(testStatus);
      }

      // Schedule next test
      const nextTestDate = new Date();
      nextTestDate.setMinutes(nextTestDate.getMinutes() + testStatus.config.test_interval_minutes);
      testStatus.next_test_date = nextTestDate.toISOString();

      // Continue loop after interval
      setTimeout(() => this.runTestLoop(testId), testStatus.config.test_interval_minutes * 60 * 1000);
      
    } catch (error) {
      console.error('Error in automated test loop:', error);
      testStatus.status = 'stopped';
    }
  }

  /**
   * Run a single backtest
   */
  private async runBacktest(
    flowId: number,
    dateRange: { start_date: string; end_date: string }
  ): Promise<any> {
    // This would call the actual backtest API
    // For now, return a placeholder
    const response = await fetch(`${API_BASE_URL}/flows/${flowId}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_data: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          // ... other backtest params
        },
      }),
    });

    if (!response.ok) {
      throw new Error('Backtest failed');
    }

    const run = await response.json();
    
    // Wait for completion and get results
    // In a real implementation, you'd poll for completion
    return {
      sharpe_ratio: run.performance_metrics?.sharpe_ratio || 0,
      total_return: run.performance_metrics?.total_return || 0,
      win_rate: run.performance_metrics?.win_rate || 0,
      max_drawdown: run.performance_metrics?.max_drawdown || 0,
    };
  }

  /**
   * Evaluate if a result meets profitability criteria
   */
  private evaluateResult(
    result: any,
    criteria: ProfitabilityCriteria
  ): boolean {
    return (
      (result.sharpe_ratio || 0) >= criteria.min_sharpe_ratio &&
      (result.win_rate || 0) >= criteria.min_win_rate &&
      (result.total_return || 0) >= criteria.min_total_return &&
      (result.max_drawdown || 0) <= criteria.max_drawdown_threshold
    );
  }

  /**
   * Check if testing has proven profitability
   */
  private isProfitable(testStatus: AutomatedTestStatus): boolean {
    const criteria = testStatus.config.profitability_criteria;
    return (
      testStatus.tests_passed >= criteria.min_tests_passed &&
      testStatus.best_result !== undefined &&
      testStatus.best_result.sharpe_ratio >= criteria.min_sharpe_ratio
    );
  }

  /**
   * Generate learning insights from test results
   */
  private generateInsights(
    testStatus: AutomatedTestStatus,
    result: any,
    passed: boolean
  ) {
    if (!testStatus.learning_insights) {
      testStatus.learning_insights = [];
    }

    if (passed) {
      testStatus.learning_insights.push(
        `✓ Test ${testStatus.total_tests}: Passed with Sharpe ${result.sharpe_ratio?.toFixed(2)} and ${(result.total_return * 100).toFixed(1)}% return`
      );
    } else {
      const issues: string[] = [];
      if ((result.sharpe_ratio || 0) < testStatus.config.profitability_criteria.min_sharpe_ratio) {
        issues.push('Low Sharpe ratio');
      }
      if ((result.win_rate || 0) < testStatus.config.profitability_criteria.min_win_rate) {
        issues.push('Low win rate');
      }
      if ((result.total_return || 0) < testStatus.config.profitability_criteria.min_total_return) {
        issues.push('Insufficient returns');
      }
      
      testStatus.learning_insights.push(
        `✗ Test ${testStatus.total_tests}: Failed - ${issues.join(', ')}`
      );
    }

    // Keep only last 20 insights
    if (testStatus.learning_insights.length > 20) {
      testStatus.learning_insights = testStatus.learning_insights.slice(-20);
    }
  }

  /**
   * Automatically adjust strategy based on failures
   */
  private async autoAdjustStrategy(testStatus: AutomatedTestStatus) {
    // This would implement logic to adjust the flow/strategy
    // For example: remove underperforming agents, adjust weights, etc.
    testStatus.adjustments_made = (testStatus.adjustments_made || 0) + 1;
    
    // Placeholder for actual adjustment logic
    console.log('Auto-adjusting strategy for test:', testStatus.id);
  }

  /**
   * Pause automated testing
   */
  pauseTesting(testId: string) {
    const test = this.activeTests.get(testId);
    if (test) {
      test.status = 'paused';
    }
  }

  /**
   * Resume automated testing
   */
  resumeTesting(testId: string) {
    const test = this.activeTests.get(testId);
    if (test && test.status === 'paused') {
      test.status = 'running';
      this.runTestLoop(testId);
    }
  }

  /**
   * Stop automated testing
   */
  stopTesting(testId: string) {
    const test = this.activeTests.get(testId);
    if (test) {
      test.status = 'stopped';
    }
  }

  /**
   * Get all active tests
   */
  getActiveTests(): AutomatedTestStatus[] {
    return Array.from(this.activeTests.values());
  }

  /**
   * Get test status
   */
  getTestStatus(testId: string): AutomatedTestStatus | undefined {
    return this.activeTests.get(testId);
  }
}

export const automatedTestingService = new AutomatedTestingService();
