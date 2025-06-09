import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Chip,
  IconButton,
  CircularProgress,
  Alert,
  InputAdornment,
} from '@mui/material';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { api, Invoice } from '../api/client';

export default function Invoices() {
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  
  const [filters, setFilters] = useState({
    search: '',
    provider: '',
    status: '',
    startDate: '',
    endDate: '',
  });

  const [providers, setProviders] = useState<string[]>([]);

  useEffect(() => {
    loadProviders();
    loadInvoices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const loadProviders = async () => {
    try {
      const data = await api.providers.getAll();
      setProviders(data);
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  };

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const params = {
        search: filters.search || undefined,
        provider: filters.provider || undefined,
        status: filters.status || undefined,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
      };
      const data = await api.invoices.getAll(params);
      setInvoices(data);
      setError(null);
    } catch (err) {
      setError('Failed to load invoices');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async (e: React.MouseEvent, invoice: Invoice) => {
    e.stopPropagation();
    try {
      await api.invoices.retry(invoice.id);
      loadInvoices();
    } catch (err) {
      console.error('Failed to retry invoice:', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return 'success';
      case 'failed':
      case 'error':
        return 'error';
      case 'pending':
      case 'processing':
        return 'warning';
      default:
        return 'default';
    }
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Invoices</Typography>
        <IconButton onClick={loadInvoices} color="primary">
          <RefreshIcon />
        </IconButton>
      </Box>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          <Grid size={12}>
            <TextField
              fullWidth
              label="Search"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid size={12}>
            <FormControl fullWidth>
              <InputLabel>Provider</InputLabel>
              <Select
                value={filters.provider}
                label="Provider"
                onChange={(e) => setFilters({ ...filters, provider: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                {providers.map((provider) => (
                  <MenuItem key={provider} value={provider}>
                    {provider.toUpperCase()}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={12}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                label="Status"
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="processing">Processing</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={12}>
            <TextField
              fullWidth
              label="Start Date"
              type="date"
              value={filters.startDate}
              onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid size={12}>
            <TextField
              fullWidth
              label="End Date"
              type="date"
              value={filters.endDate}
              onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
        </Grid>
      </Paper>

      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Invoice ID</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Amount</TableCell>
                <TableCell>Provider</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices
                .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                .map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    hover
                    onClick={() => navigate(`/invoices/${invoice.id}`)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{invoice.stripe_invoice_id}</TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{invoice.customer_name}</Typography>
                        <Typography variant="caption" color="textSecondary">
                          {invoice.customer_email}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      {invoice.currency.toUpperCase()} {(invoice.amount / 100).toFixed(2)}
                    </TableCell>
                    <TableCell>{invoice.provider.toUpperCase()}</TableCell>
                    <TableCell>
                      <Chip
                        label={invoice.status}
                        color={getStatusColor(invoice.status)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      {format(new Date(invoice.created_at), 'MMM dd, yyyy HH:mm')}
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/invoices/${invoice.id}`);
                        }}
                      >
                        <VisibilityIcon />
                      </IconButton>
                      {invoice.status === 'failed' && (
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={(e) => handleRetry(e, invoice)}
                        >
                          <RefreshIcon />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              {invoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    No invoices found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[5, 10, 25]}
            component="div"
            count={invoices.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </TableContainer>
      )}
    </Box>
  );
}