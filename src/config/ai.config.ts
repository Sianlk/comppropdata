// AI Configuration — CompProp Data
// Domain: real estate | Focus: property valuation, market analysis, investment scoring

export const AI_CONFIG = {
  baseURL: process.env.EXPO_PUBLIC_API_URL ?? 'https://api.sianlk.com',
  models: {
    primary: 'gpt-4o',
    fast: 'gpt-4o-mini',
    embedding: 'text-embedding-3-large',
    vision: 'gpt-4o',
  },
  domain: 'real estate',
  focus: 'property valuation, market analysis, investment scoring',
  features: {
    streamingEnabled: true,
    voiceEnabled: true,
    visionEnabled: true,
    agentsEnabled: true,
  },
  rateLimit: {
    requestsPerMinute: 60,
    tokensPerRequest: 4096,
    maxRetries: 3,
  },
  workforce: {
    orchestratorEnabled: true,
    maxConcurrentAgents: 5,
    agentTimeout: 30000,
  },
};

export default AI_CONFIG;
