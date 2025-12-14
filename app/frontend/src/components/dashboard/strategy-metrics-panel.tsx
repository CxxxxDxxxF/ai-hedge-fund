import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  TrendingUp, TrendingDown, Target, AlertCircle, Clock, 
  BarChart3, DollarSign, Activity, Zap, Shield
} from 'lucide-react';
import { useEffect, useState } from 'react';

interface StrategyMetricsPanelProps {
  performanceMetrics?: {
    sharpe_ratio?: number;
    sortino_ratio?: number;
    max_drawdown?: number;
    total_return?: number;
    win_rate?: number;
    total_trades?: number;
    // Funded-account metrics
    time_to_recovery?: number; // days
    losing_streaks?: number;
    profitable_days_pct?: number;
    largest_winning_day?: number;
    largest_losing_day?: number;
    average_win?: number;
    average_loss?: number;
    profit_factor?: number;
    expectancy?: number;
    // Topstep-specific
    opening_range_breaks?: number;
    pullback_entries?: number;
    regime_filter_passes?: number;
    daily_trade_limit_hits?: number;
  };
  strategyType?: 'topstep' | 'simple' | 'portfolio_manager';
}

// Animated number counter component
function AnimatedNumber({ value, decimals = 2, prefix = '', suffix = '', className = '' }: {
  value: number | undefined;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}) {
  const [displayValue, setDisplayValue] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (value === undefined) return;
    
    setIsAnimating(true);
    const duration = 1000; // 1 second
    const steps = 60;
    const stepValue = value / steps;
    const stepDuration = duration / steps;
    
    let currentStep = 0;
    const interval = setInterval(() => {
      currentStep++;
      const newValue = Math.min(stepValue * currentStep, value);
      setDisplayValue(newValue);
      
      if (currentStep >= steps) {
        clearInterval(interval);
        setDisplayValue(value);
        setTimeout(() => setIsAnimating(false), 100);
      }
    }, stepDuration);
    
    return () => clearInterval(interval);
  }, [value]);

  if (value === undefined) return <span className={className}>N/A</span>;
  
  return (
    <span className={`${className} ${isAnimating ? 'animate-pulse' : ''}`}>
      {prefix}{displayValue.toFixed(decimals)}{suffix}
    </span>
  );
}

export function StrategyMetricsPanel({ performanceMetrics, strategyType = 'portfolio_manager' }: StrategyMetricsPanelProps) {
  if (!performanceMetrics) {
    return (
      <Card className="bg-panel border-gray-700 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BarChart3 className="h-5 w-5 animate-pulse" />
            Strategy Performance Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No metrics available. Run a backtest to see performance metrics.
          </div>
        </CardContent>
      </Card>
    );
  }

  const {
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    total_return,
    win_rate,
    total_trades,
    time_to_recovery,
    losing_streaks,
    profitable_days_pct,
    largest_winning_day,
    largest_losing_day,
    average_win,
    average_loss,
    profit_factor,
    expectancy,
    opening_range_breaks,
    pullback_entries,
    regime_filter_passes,
    daily_trade_limit_hits,
  } = performanceMetrics;

  return (
    <Card className="bg-panel border-gray-700 animate-in fade-in slide-in-from-bottom-4 duration-500 hover:shadow-lg transition-shadow">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <BarChart3 className="h-5 w-5 animate-pulse" />
          Strategy Performance Metrics
          {strategyType === 'topstep' && (
            <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/50 ml-2 animate-in fade-in zoom-in duration-300">
              Topstep Strategy
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Core Performance Metrics */}
          <div className="animate-in fade-in slide-in-from-left-4 duration-700 delay-100">
            <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 animate-bounce" />
              Core Performance
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-200">
                <p className="text-xs text-muted-foreground mb-1">Total Return</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${total_return && total_return > 0 ? 'text-green-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={total_return} suffix="%" decimals={2} />
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-300">
                <p className="text-xs text-muted-foreground mb-1">Sharpe Ratio</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${sharpe_ratio && sharpe_ratio > 1 ? 'text-green-500' : sharpe_ratio && sharpe_ratio > 0 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={sharpe_ratio} decimals={2} />
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-400">
                <p className="text-xs text-muted-foreground mb-1">Max Drawdown</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${max_drawdown && max_drawdown > -15 ? 'text-green-500' : max_drawdown && max_drawdown > -25 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={max_drawdown} suffix="%" decimals={2} />
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-500">
                <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${win_rate && win_rate > 50 ? 'text-green-500' : win_rate && win_rate > 40 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={win_rate} suffix="%" decimals={1} />
                </p>
              </div>
            </div>
          </div>

          {/* Funded-Account Critical Metrics */}
          <div className="animate-in fade-in slide-in-from-right-4 duration-700 delay-200">
            <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
              <Shield className="h-4 w-4 animate-pulse" />
              Funded-Account Survival Metrics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-300">
                <p className="text-xs text-muted-foreground mb-1">Time to Recovery</p>
                <p className="text-lg font-bold text-primary">
                  {time_to_recovery !== undefined ? (
                    <>
                      <AnimatedNumber value={time_to_recovery} suffix=" days" decimals={0} />
                    </>
                  ) : 'N/A'}
                </p>
                {time_to_recovery !== undefined && time_to_recovery > 30 && (
                  <p className="text-xs text-yellow-500 mt-1 animate-pulse">⚠️ Slow recovery</p>
                )}
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-400">
                <p className="text-xs text-muted-foreground mb-1">Losing Streaks</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${losing_streaks && losing_streaks < 3 ? 'text-green-500' : losing_streaks && losing_streaks < 5 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={losing_streaks} decimals={0} />
                </p>
                {losing_streaks !== undefined && losing_streaks >= 3 && (
                  <p className="text-xs text-red-500 mt-1 animate-pulse">⚠️ High streak risk</p>
                )}
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-500">
                <p className="text-xs text-muted-foreground mb-1">Profitable Days</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${profitable_days_pct && profitable_days_pct > 60 ? 'text-green-500' : profitable_days_pct && profitable_days_pct > 50 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={profitable_days_pct} suffix="%" decimals={1} />
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border hover:scale-105 hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 delay-600">
                <p className="text-xs text-muted-foreground mb-1">Profit Factor</p>
                <p className={`text-lg font-bold transition-colors duration-300 ${profit_factor && profit_factor > 1.5 ? 'text-green-500' : profit_factor && profit_factor > 1.0 ? 'text-yellow-500' : 'text-red-500'}`}>
                  <AnimatedNumber value={profit_factor} decimals={2} />
                </p>
              </div>
            </div>
          </div>

          {/* R-Multiple & Expectancy */}
          <div>
            <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
              <Target className="h-4 w-4" />
              Risk-Adjusted Metrics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Average Win</p>
                <p className="text-lg font-bold text-green-500">
                  {average_win !== undefined ? `$${average_win.toFixed(2)}` : 'N/A'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Average Loss</p>
                <p className="text-lg font-bold text-red-500">
                  {average_loss !== undefined ? `$${Math.abs(average_loss).toFixed(2)}` : 'N/A'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Expectancy</p>
                <p className={`text-lg font-bold ${expectancy && expectancy > 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {expectancy !== undefined ? `$${expectancy.toFixed(2)}` : 'N/A'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Largest Win Day</p>
                <p className="text-lg font-bold text-green-500">
                  {largest_winning_day !== undefined ? `$${largest_winning_day.toFixed(2)}` : 'N/A'}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Largest Loss Day</p>
                <p className="text-lg font-bold text-red-500">
                  {largest_losing_day !== undefined ? `$${Math.abs(largest_losing_day).toFixed(2)}` : 'N/A'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-background/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">Total Trades</p>
                <p className="text-lg font-bold text-primary">
                  {total_trades !== undefined ? total_trades : 'N/A'}
                </p>
              </div>
            </div>
          </div>

          {/* Topstep Strategy Specific Metrics */}
          {strategyType === 'topstep' && (
            <div>
              <h3 className="text-sm font-semibold text-primary mb-3 flex items-center gap-2">
                <Zap className="h-4 w-4" />
                Topstep Strategy Details
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                  <p className="text-xs text-muted-foreground mb-1">Opening Range Breaks</p>
                  <p className="text-lg font-bold text-blue-500">
                    {opening_range_breaks !== undefined ? opening_range_breaks : 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                  <p className="text-xs text-muted-foreground mb-1">Pullback Entries</p>
                  <p className="text-lg font-bold text-blue-500">
                    {pullback_entries !== undefined ? pullback_entries : 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                  <p className="text-xs text-muted-foreground mb-1">Regime Filter Passes</p>
                  <p className="text-lg font-bold text-blue-500">
                    {regime_filter_passes !== undefined ? regime_filter_passes : 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                  <p className="text-xs text-muted-foreground mb-1">Daily Limit Hits</p>
                  <p className="text-lg font-bold text-yellow-500">
                    {daily_trade_limit_hits !== undefined ? daily_trade_limit_hits : 'N/A'}
                  </p>
                </div>
              </div>
              <div className="mt-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/50">
                <p className="text-xs text-muted-foreground mb-2">Strategy Rules</p>
                <ul className="text-xs space-y-1 text-primary">
                  <li>• Risk: 0.25% per trade</li>
                  <li>• Max 1 trade per day</li>
                  <li>• Max 0.5R loss per day</li>
                  <li>• Profit target: 1.5R</li>
                  <li>• Stop after win: Yes</li>
                </ul>
              </div>
            </div>
          )}

          {/* Risk Warnings */}
          {(max_drawdown && max_drawdown < -15) || (losing_streaks && losing_streaks >= 3) || (profitable_days_pct && profitable_days_pct < 50) ? (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/50 animate-in fade-in slide-in-from-bottom-4 duration-500 hover:scale-[1.02] transition-transform">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 animate-pulse" />
                <div>
                  <p className="text-sm font-semibold text-red-500 mb-2">Risk Warnings</p>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    {max_drawdown && max_drawdown < -15 && (
                      <li className="animate-in fade-in slide-in-from-left-2 delay-100">⚠️ Max drawdown exceeds 15% - funded account risk</li>
                    )}
                    {losing_streaks && losing_streaks >= 3 && (
                      <li className="animate-in fade-in slide-in-from-left-2 delay-200">⚠️ Losing streak of {losing_streaks} - funded account limit risk</li>
                    )}
                    {profitable_days_pct && profitable_days_pct < 50 && (
                      <li className="animate-in fade-in slide-in-from-left-2 delay-300">⚠️ Less than 50% profitable days - consistency concern</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
