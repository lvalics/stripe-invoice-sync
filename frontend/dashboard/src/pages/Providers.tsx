import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  CircularProgress,
  Alert,
  Chip,
  Paper,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { api, ProviderStats } from '../api/client';

interface ProviderStatus {
  name: string;
  isValid: boolean;
  error?: string;
  stats?: ProviderStats;
}

export default function Providers() {
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState<string | null>(null);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      setLoading(true);
      const providerList = await api.providers.getAll();
      const stats = await api.dashboard.getStats();
      
      const providerStatuses: ProviderStatus[] = await Promise.all(
        providerList.map(async (provider) => {
          try {
            await api.providers.validate(provider);
            const providerStats = stats.providers.find(p => p.provider === provider);
            return {
              name: provider,
              isValid: true,
              stats: providerStats,
            };
          } catch (err: any) {
            return {
              name: provider,
              isValid: false,
              error: err.response?.data?.detail || 'Validation failed',
            };
          }
        })
      );
      
      setProviders(providerStatuses);
    } catch (err) {
      console.error('Failed to load providers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async (provider: string) => {
    try {
      setValidating(provider);
      await api.providers.validate(provider);
      
      // Reload providers to update status
      await loadProviders();
    } catch (err) {
      console.error(`Failed to validate ${provider}:`, err);
    } finally {
      setValidating(null);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Providers
      </Typography>
      
      <Grid container spacing={3}>
        {providers.map((provider) => (
          <Grid size={{ xs: 12, md: 6 }} key={provider.name}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Typography variant="h6">
                      {provider.name.toUpperCase()}
                    </Typography>
                    <Chip
                      icon={provider.isValid ? <CheckCircleIcon /> : <ErrorIcon />}
                      label={provider.isValid ? 'Active' : 'Inactive'}
                      color={provider.isValid ? 'success' : 'error'}
                      size="small"
                    />
                  </Box>
                  <Button
                    size="small"
                    startIcon={<SettingsIcon />}
                    onClick={() => handleValidate(provider.name)}
                    disabled={validating === provider.name}
                  >
                    {validating === provider.name ? 'Validating...' : 'Validate'}
                  </Button>
                </Box>
                
                {provider.error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {provider.error}
                  </Alert>
                )}
                
                {provider.stats && (
                  <Box>
                    <Grid container spacing={2}>
                      <Grid size={6}>
                        <Typography variant="body2" color="textSecondary">
                          Total Invoices
                        </Typography>
                        <Typography variant="h6">
                          {provider.stats.total_invoices}
                        </Typography>
                      </Grid>
                      <Grid size={6}>
                        <Typography variant="body2" color="textSecondary">
                          Success Rate
                        </Typography>
                        <Typography variant="h6">
                          {provider.stats.success_rate.toFixed(1)}%
                        </Typography>
                      </Grid>
                    </Grid>
                    
                    <Box mt={2}>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">Status Distribution</Typography>
                      </Box>
                      <Box display="flex" gap={1} alignItems="center">
                        <Box flex={provider.stats.successful} bgcolor="success.main" height={8} />
                        <Box flex={provider.stats.failed} bgcolor="error.main" height={8} />
                        <Box flex={provider.stats.pending} bgcolor="warning.main" height={8} />
                      </Box>
                      <Box display="flex" justifyContent="space-between" mt={1}>
                        <Typography variant="caption" color="success.main">
                          Success: {provider.stats.successful}
                        </Typography>
                        <Typography variant="caption" color="error.main">
                          Failed: {provider.stats.failed}
                        </Typography>
                        <Typography variant="caption" color="warning.main">
                          Pending: {provider.stats.pending}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
        
        {providers.length === 0 && (
          <Grid size={12}>
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="textSecondary">
                No providers configured
              </Typography>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}