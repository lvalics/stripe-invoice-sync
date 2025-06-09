import React, { useEffect, useState } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import { api, DashboardStats } from '../api/client';

const COLORS = {
  success: '#4caf50',
  failed: '#f44336',
  pending: '#ff9800',
  processing: '#2196f3',
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardStats();
  }, []);

  const loadDashboardStats = async () => {
    try {
      setLoading(true);
      const data = await api.dashboard.getStats();
      setStats(data);
      setError(null);
    } catch (err) {
      setError('Failed to load dashboard statistics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !stats) {
    return <Alert severity="error">{error || 'No data available'}</Alert>;
  }

  const pieData = stats.providers.map(p => ({
    name: p.provider.toUpperCase(),
    value: p.total_invoices,
  }));

  const barData = stats.providers.map(p => ({
    provider: p.provider.toUpperCase(),
    successful: p.successful,
    failed: p.failed,
    pending: p.pending,
  }));

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Invoices
              </Typography>
              <Typography variant="h3">
                {stats.total_invoices}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Amount
              </Typography>
              <Typography variant="h3">
                €{(stats.total_amount / 100).toFixed(2)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Active Providers
              </Typography>
              <Typography variant="h3">
                {stats.providers.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Success Rate
              </Typography>
              <Typography variant="h3">
                {stats.total_invoices > 0
                  ? Math.round(
                      (stats.providers.reduce((acc, p) => acc + p.successful, 0) /
                        stats.total_invoices) *
                        100
                    )
                  : 0}
                %
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Invoices by Provider
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value, percent }) =>
                    `${name}: ${value} (${(percent * 100).toFixed(0)}%)`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index === 0 ? COLORS.processing : COLORS.pending}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Invoice Status by Provider
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="provider" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="successful" fill={COLORS.success} />
                <Bar dataKey="failed" fill={COLORS.failed} />
                <Bar dataKey="pending" fill={COLORS.pending} />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid size={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Recent Activity
            </Typography>
            {stats.recent_activity.length > 0 ? (
              <Box>
                {stats.recent_activity.map((activity) => (
                  <Box
                    key={activity.id}
                    sx={{
                      py: 1,
                      borderBottom: '1px solid #e0e0e0',
                      '&:last-child': { borderBottom: 0 },
                    }}
                  >
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2">
                        Invoice #{activity.invoice_id} - {activity.action}
                      </Typography>
                      <Typography
                        variant="body2"
                        color={activity.status === 'success' ? 'success.main' : 'error.main'}
                      >
                        {activity.status}
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="textSecondary">
                      {format(new Date(activity.created_at), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography color="textSecondary">No recent activity</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}