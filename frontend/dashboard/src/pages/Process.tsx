import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Search as SearchIcon,
  PlayArrow as ProcessIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { api } from '../api/client';

interface StripeInvoice {
  id: string;
  number: string;
  customer: string;
  customer_email: string;
  customer_name: string;
  amount_paid: number;
  amount_total?: number;
  amount_refunded?: number;
  currency: string;
  status: string;
  original_status?: string;
  refunded?: boolean;
  created: number;
  period_start: number;
  period_end: number;
  lines: Array<{
    description: string;
    amount: number;
  }>;
  source_type?: 'invoice' | 'charge';
}

export default function Process() {
  const [filters, setFilters] = useState({
    startDate: format(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
    endDate: format(new Date(), 'yyyy-MM-dd'),
    customerId: '',
    status: '',
    type: 'invoices' as 'invoices' | 'charges' | 'both',
  });

  const [stripeInvoices, setStripeInvoices] = useState<StripeInvoice[]>([]);
  const [selectedInvoices, setSelectedInvoices] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processResult, setProcessResult] = useState<any>(null);
  const [provider, setProvider] = useState('anaf');
  const [providers, setProviders] = useState<string[]>([]);

  React.useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await api.providers.getAll();
      setProviders(data);
      if (data.length > 0 && !provider) {
        setProvider(data[0]);
      }
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  };

  const handleSearch = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        start_date: filters.startDate,
        end_date: filters.endDate,
        customer_id: filters.customerId || undefined,
        status: filters.status || undefined,
      };
      
      let invoices: StripeInvoice[] = [];
      let charges: StripeInvoice[] = [];
      
      if (filters.type === 'invoices' || filters.type === 'both') {
        try {
          const invoiceResponse = await api.stripe.getInvoices(params);
          invoices = invoiceResponse.map((inv: any) => ({
            ...inv,
            source_type: 'invoice'
          }));
        } catch (err) {
          console.error('Failed to fetch invoices:', err);
        }
      }
      
      if (filters.type === 'charges' || filters.type === 'both') {
        try {
          const chargeResponse = await api.stripe.getCharges(params);
          charges = chargeResponse.map((charge: any) => ({
            id: charge.id,
            number: charge.id,
            customer: charge.customer || '',
            customer_email: charge.customer_email || '',
            customer_name: charge.customer_name || '',
            amount_paid: charge.amount - (charge.amount_refunded || 0),
            amount_total: charge.amount,
            amount_refunded: charge.amount_refunded || 0,
            currency: charge.currency,
            status: charge.status,
            original_status: charge.original_status,
            refunded: charge.refunded,
            created: charge.created,
            period_start: charge.created,
            period_end: charge.created,
            lines: [{
              description: charge.description || 'Charge',
              amount: charge.amount
            }],
            source_type: 'charge'
          }));
        } catch (err) {
          console.error('Failed to fetch charges:', err);
        }
      }
      
      const combined = [...invoices, ...charges].sort((a, b) => b.created - a.created);
      setStripeInvoices(combined);
      setSelectedInvoices(new Set());
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch data from Stripe');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelectedInvoices(new Set(stripeInvoices.map(inv => inv.id)));
    } else {
      setSelectedInvoices(new Set());
    }
  };

  const handleSelectInvoice = (invoiceId: string) => {
    const newSelected = new Set(selectedInvoices);
    if (newSelected.has(invoiceId)) {
      newSelected.delete(invoiceId);
    } else {
      newSelected.add(invoiceId);
    }
    setSelectedInvoices(newSelected);
  };

  const handleProcessSelected = async () => {
    if (selectedInvoices.size === 0) {
      setError('Please select at least one invoice to process');
      return;
    }

    try {
      setProcessing(true);
      setError(null);
      setProcessResult(null);
      
      const response = await api.stripe.processInvoices({
        invoice_ids: Array.from(selectedInvoices),
        provider,
      });
      
      setProcessResult(response);
      setSelectedInvoices(new Set());
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to process invoices');
      console.error(err);
    } finally {
      setProcessing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
      case 'succeeded':
        return 'success';
      case 'refunded':
        return 'error';
      case 'partially_refunded':
        return 'warning';
      case 'open':
      case 'pending':
        return 'info';
      case 'void':
      case 'uncollectible':
      case 'failed':
        return 'error';
      case 'draft':
        return 'default';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Process Stripe Invoices
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Search Filters
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <FormControl fullWidth>
              <InputLabel>Type</InputLabel>
              <Select
                value={filters.type}
                label="Type"
                onChange={(e) => setFilters({ ...filters, type: e.target.value as 'invoices' | 'charges' | 'both' })}
              >
                <MenuItem value="invoices">Invoices Only</MenuItem>
                <MenuItem value="charges">Charges Only</MenuItem>
                <MenuItem value="both">Both (Invoices & Charges)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 2 }}>
            <TextField
              fullWidth
              label="Start Date"
              type="date"
              value={filters.startDate}
              onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 2 }}>
            <TextField
              fullWidth
              label="End Date"
              type="date"
              value={filters.endDate}
              onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 2 }}>
            <TextField
              fullWidth
              label="Customer ID"
              value={filters.customerId}
              onChange={(e) => setFilters({ ...filters, customerId: e.target.value })}
              placeholder="cus_..."
            />
          </Grid>
          <Grid size={{ xs: 12, md: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                label="Status"
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="draft">Draft</MenuItem>
                <MenuItem value="open">Open</MenuItem>
                <MenuItem value="paid">Paid</MenuItem>
                <MenuItem value="refunded">Refunded</MenuItem>
                <MenuItem value="partially_refunded">Partially Refunded</MenuItem>
                <MenuItem value="void">Void</MenuItem>
                <MenuItem value="uncollectible">Uncollectible</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={12}>
            <Box display="flex" gap={2} alignItems="center">
              <Button
                variant="contained"
                startIcon={<SearchIcon />}
                onClick={handleSearch}
                disabled={loading}
              >
                Search Stripe
              </Button>
              <Button
                variant="outlined"
                startIcon={<ClearIcon />}
                onClick={() => {
                  setFilters({
                    startDate: format(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
                    endDate: format(new Date(), 'yyyy-MM-dd'),
                    customerId: '',
                    status: '',
                    type: 'invoices',
                  });
                  setStripeInvoices([]);
                  setSelectedInvoices(new Set());
                }}
              >
                Clear
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {processResult && (
        <Alert 
          severity={processResult.failed === 0 ? 'success' : 'warning'} 
          sx={{ mb: 2 }}
          onClose={() => setProcessResult(null)}
        >
          Processed {processResult.total} invoices: {processResult.successful} successful, {processResult.failed} failed
        </Alert>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : stripeInvoices.length > 0 ? (
        <>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              Found {stripeInvoices.length} invoices
            </Typography>
            <Box display="flex" gap={2} alignItems="center">
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Provider</InputLabel>
                <Select
                  value={provider}
                  label="Provider"
                  onChange={(e) => setProvider(e.target.value)}
                >
                  {providers.map((p) => (
                    <MenuItem key={p} value={p}>
                      {p.toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button
                variant="contained"
                color="primary"
                startIcon={<ProcessIcon />}
                onClick={handleProcessSelected}
                disabled={selectedInvoices.size === 0 || processing}
              >
                Process Selected ({selectedInvoices.size})
              </Button>
            </Box>
          </Box>

          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      indeterminate={selectedInvoices.size > 0 && selectedInvoices.size < stripeInvoices.length}
                      checked={stripeInvoices.length > 0 && selectedInvoices.size === stripeInvoices.length}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>ID/Number</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Period</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stripeInvoices.map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    hover
                    selected={selectedInvoices.has(invoice.id)}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedInvoices.has(invoice.id)}
                        onChange={() => handleSelectInvoice(invoice.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={invoice.source_type === 'charge' ? 'Charge' : 'Invoice'}
                        size="small"
                        color={invoice.source_type === 'charge' ? 'secondary' : 'primary'}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{invoice.number || invoice.id}</Typography>
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{invoice.customer_name || 'N/A'}</Typography>
                        <Typography variant="caption" color="textSecondary">
                          {invoice.customer_email}
                        </Typography>
                        <Typography variant="caption" display="block" color="textSecondary">
                          {invoice.customer}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">
                          {invoice.currency.toUpperCase()} {(invoice.amount_paid / 100).toFixed(2)}
                        </Typography>
                        {invoice.amount_refunded && invoice.amount_refunded > 0 && (
                          <Typography variant="caption" color="error">
                            Refunded: {(invoice.amount_refunded / 100).toFixed(2)}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={invoice.status}
                        color={getStatusColor(invoice.status)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      {format(new Date(invoice.created * 1000), 'MMM dd, yyyy')}
                    </TableCell>
                    <TableCell>
                      <Tooltip title={`${format(new Date(invoice.period_start * 1000), 'MMM dd, yyyy')} - ${format(new Date(invoice.period_end * 1000), 'MMM dd, yyyy')}`}>
                        <Typography variant="caption">
                          {format(new Date(invoice.period_start * 1000), 'MMM dd')} - {format(new Date(invoice.period_end * 1000), 'MMM dd')}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="textSecondary">
            Use the search filters above to fetch invoices from Stripe
          </Typography>
        </Paper>
      )}
    </Box>
  );
}