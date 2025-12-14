import { Agent } from './agents';

export enum Rank {
  INTERN = 'Intern',
  ANALYST = 'Analyst',
  SENIOR_ANALYST = 'Senior Analyst',
  ASSOCIATE = 'Associate',
  VICE_PRESIDENT = 'Vice President',
  DIRECTOR = 'Director',
  MANAGING_DIRECTOR = 'Managing Director',
  PARTNER = 'Partner',
}

export enum Authority {
  READ_ONLY = 'Read Only',
  RESEARCH = 'Research',
  ANALYSIS = 'Analysis',
  RECOMMENDATION = 'Recommendation',
  TRADING_DECISION = 'Trading Decision',
  PORTFOLIO_MANAGEMENT = 'Portfolio Management',
  RISK_MANAGEMENT = 'Risk Management',
  EXECUTIVE = 'Executive',
}

export interface Department {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: 'DollarSign' | 'TrendingUp' | 'BarChart3' | 'Calculator' | 'Shield' | 'Globe' | 'ClipboardCheck';
}

export interface AgentRole {
  agent_key: string;
  department: Department;
  rank: Rank;
  authority: Authority;
  experience_level: number; // 1-10
  specialization: string;
}

// Department definitions
export const DEPARTMENTS: Department[] = [
  {
    id: 'value',
    name: 'Value Investing',
    description: 'Fundamental analysis and value-based investment strategies',
    color: 'blue',
    icon: 'DollarSign',
  },
  {
    id: 'growth',
    name: 'Growth Investing',
    description: 'Growth-oriented analysis and momentum strategies',
    color: 'green',
    icon: 'TrendingUp',
  },
  {
    id: 'technical',
    name: 'Technical Analysis',
    description: 'Chart analysis, momentum, and technical indicators',
    color: 'purple',
    icon: 'BarChart3',
  },
  {
    id: 'quantitative',
    name: 'Quantitative Research',
    description: 'Statistical analysis, mean reversion, and algorithmic strategies',
    color: 'orange',
    icon: 'Calculator',
  },
  {
    id: 'risk',
    name: 'Risk Management',
    description: 'Risk assessment, position sizing, and portfolio protection',
    color: 'red',
    icon: 'Shield',
  },
  {
    id: 'macro',
    name: 'Macro Analysis',
    description: 'Market regime analysis and macroeconomic trends',
    color: 'yellow',
    icon: 'Globe',
  },
  {
    id: 'performance',
    name: 'Performance Audit',
    description: 'Performance tracking and analyst evaluation',
    color: 'gray',
    icon: 'ClipboardCheck',
  },
];

// Map agents to departments and assign ranks
export function assignAgentRole(agent: Agent): AgentRole {
  const key = agent.key.toLowerCase();
  const style = agent.investing_style.toLowerCase();
  const name = agent.display_name.toLowerCase();

  // Determine department
  let department: Department;
  let rank: Rank;
  let authority: Authority;
  let experience_level: number;
  let specialization: string;

  // Value Investing Department
  if (
    key.includes('warren') || key.includes('buffett') ||
    key.includes('graham') || key.includes('munger') ||
    key.includes('burry') || key.includes('pabrai') ||
    key.includes('damodaran') ||
    style.includes('value') || style.includes('fundamental')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'value')!;
    
    if (key.includes('warren') || key.includes('buffett')) {
      rank = Rank.PARTNER;
      authority = Authority.EXECUTIVE;
      experience_level = 10;
      specialization = 'Value Composite Strategy';
    } else if (key.includes('damodaran')) {
      rank = Rank.MANAGING_DIRECTOR;
      authority = Authority.PORTFOLIO_MANAGEMENT;
      experience_level = 9;
      specialization = 'Valuation Expert';
    } else {
      rank = Rank.DIRECTOR;
      authority = Authority.RECOMMENDATION;
      experience_level = 8;
      specialization = 'Value Analysis';
    }
  }
  // Growth Investing Department
  else if (
    key.includes('lynch') || key.includes('wood') ||
    key.includes('fisher') || key.includes('growth') ||
    style.includes('growth')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'growth')!;
    
    if (key.includes('lynch')) {
      rank = Rank.MANAGING_DIRECTOR;
      authority = Authority.PORTFOLIO_MANAGEMENT;
      experience_level = 9;
      specialization = 'Growth Composite Strategy';
    } else {
      rank = Rank.DIRECTOR;
      authority = Authority.RECOMMENDATION;
      experience_level = 7;
      specialization = 'Growth Analysis';
    }
  }
  // Technical Analysis Department
  else if (
    key.includes('momentum') || key.includes('technical') ||
    key.includes('trend') || style.includes('momentum') ||
    style.includes('technical')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'technical')!;
    
    if (key.includes('momentum') && !key.includes('cross')) {
      rank = Rank.VICE_PRESIDENT;
      authority = Authority.TRADING_DECISION;
      experience_level = 7;
      specialization = 'Price Momentum';
    } else if (key.includes('cross')) {
      rank = Rank.SENIOR_ANALYST;
      authority = Authority.ANALYSIS;
      experience_level = 6;
      specialization = 'Cross-Sectional Momentum';
    } else {
      rank = Rank.ANALYST;
      authority = Authority.ANALYSIS;
      experience_level = 5;
      specialization = 'Technical Analysis';
    }
  }
  // Quantitative Research Department
  else if (
    key.includes('mean') || key.includes('reversion') ||
    key.includes('volatility') || key.includes('neutral') ||
    key.includes('regime') && key.includes('conditional') ||
    style.includes('statistical') || style.includes('quantitative') ||
    style.includes('algorithmic')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'quantitative')!;
    
    if (key.includes('regime') && key.includes('conditional')) {
      rank = Rank.DIRECTOR;
      authority = Authority.RISK_MANAGEMENT;
      experience_level = 8;
      specialization = 'Regime-Adjusted Strategies';
    } else if (key.includes('neutral')) {
      rank = Rank.VICE_PRESIDENT;
      authority = Authority.TRADING_DECISION;
      experience_level = 7;
      specialization = 'Market-Neutral Strategies';
    } else if (key.includes('volatility')) {
      rank = Rank.SENIOR_ANALYST;
      authority = Authority.ANALYSIS;
      experience_level = 6;
      specialization = 'Volatility Analysis';
    } else {
      rank = Rank.ANALYST;
      authority = Authority.ANALYSIS;
      experience_level = 5;
      specialization = 'Mean Reversion';
    }
  }
  // Risk Management Department
  else if (
    key.includes('preservation') || key.includes('drawdown') ||
    key.includes('risk') || style.includes('risk') ||
    style.includes('preservation')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'risk')!;
    rank = Rank.MANAGING_DIRECTOR;
    authority = Authority.RISK_MANAGEMENT;
    experience_level = 9;
    specialization = 'Capital Preservation';
  }
  // Macro Analysis Department
  else if (
    key.includes('regime') || key.includes('market') ||
    style.includes('macro') || style.includes('regime')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'macro')!;
    rank = Rank.DIRECTOR;
    authority = Authority.RECOMMENDATION;
    experience_level = 8;
    specialization = 'Market Regime Analysis';
  }
  // Performance Audit Department
  else if (
    key.includes('audit') || key.includes('performance') ||
    style.includes('tracking') || style.includes('audit')
  ) {
    department = DEPARTMENTS.find(d => d.id === 'performance')!;
    rank = Rank.VICE_PRESIDENT;
    authority = Authority.RISK_MANAGEMENT;
    experience_level = 7;
    specialization = 'Performance Tracking';
  }
  // Default assignment
  else {
    department = DEPARTMENTS.find(d => d.id === 'quantitative')!;
    rank = Rank.ANALYST;
    authority = Authority.ANALYSIS;
    experience_level = 5;
    specialization = 'General Analysis';
  }

  return {
    agent_key: agent.key,
    department,
    rank,
    authority,
    experience_level,
    specialization,
  };
}

// Get department color classes
export function getDepartmentColorClass(department: Department): string {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500/10 border-blue-500/50 text-blue-500',
    green: 'bg-green-500/10 border-green-500/50 text-green-500',
    purple: 'bg-purple-500/10 border-purple-500/50 text-purple-500',
    orange: 'bg-orange-500/10 border-orange-500/50 text-orange-500',
    red: 'bg-red-500/10 border-red-500/50 text-red-500',
    yellow: 'bg-yellow-500/10 border-yellow-500/50 text-yellow-500',
    gray: 'bg-gray-500/10 border-gray-500/50 text-gray-500',
  };
  return colorMap[department.color] || colorMap.gray;
}

// Get rank badge color
export function getRankColor(rank: Rank): string {
  const rankMap: Record<Rank, string> = {
    [Rank.INTERN]: 'bg-gray-500/20 text-gray-500 border-gray-500/50',
    [Rank.ANALYST]: 'bg-blue-500/20 text-blue-500 border-blue-500/50',
    [Rank.SENIOR_ANALYST]: 'bg-green-500/20 text-green-500 border-green-500/50',
    [Rank.ASSOCIATE]: 'bg-purple-500/20 text-purple-500 border-purple-500/50',
    [Rank.VICE_PRESIDENT]: 'bg-orange-500/20 text-orange-500 border-orange-500/50',
    [Rank.DIRECTOR]: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50',
    [Rank.MANAGING_DIRECTOR]: 'bg-red-500/20 text-red-500 border-red-500/50',
    [Rank.PARTNER]: 'bg-indigo-500/20 text-indigo-500 border-indigo-500/50',
  };
  return rankMap[rank] || rankMap[Rank.ANALYST];
}
